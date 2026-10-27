import io
import struct
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capture_session_v4 import run_capture


def pcap_header():
    return b"\xd4\xc3\xb2\xa1" + struct.pack("<HHIIII", 2, 4, 0, 0, 65535, 1)


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def monotonic(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds

    def now(self):
        start = datetime(2026, 10, 27, tzinfo=timezone.utc)
        return (start + timedelta(seconds=self.value)).isoformat().replace("+00:00", "Z")


class FakeProcess:
    pid = 12345

    def __init__(self):
        self.returncode = None
        self.stderr = io.StringIO(
            "0 packets captured\n0 packets received by filter\n0 packets dropped by kernel\n"
        )

    def poll(self):
        return self.returncode


class CaptureSessionTests(unittest.TestCase):
    def run_fake(self, *, delayed=False, interrupt=False):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        output = Path(temp.name) / "synthetic.pcap"
        clock = FakeClock()
        process = FakeProcess()

        def popen(command, **_kwargs):
            output.write_bytes(pcap_header())
            return process

        probe_calls = {"count": 0}

        def probe(_pgid):
            probe_calls["count"] += 1
            if delayed and probe_calls["count"] < 3:
                return {"processes": [], "scan_complete": True, "errors": []}
            return {
                "processes": [{"pid": 12346, "active": True}],
                "scan_complete": True,
                "errors": [],
            }

        stopped = {"value": False}

        def stop(_process):
            stopped["value"] = True
            process.returncode = 0
            clock.value += 4  # shutdown time must not extend the effective capture window
            return {"cleanup_completed": True, "sigint_attempted": True}

        signal_checks = {"count": 0}

        def stop_requested():
            signal_checks["count"] += 1
            if interrupt and signal_checks["count"] >= 3:
                return "SIGTERM"
            return None

        report = run_capture(
            session_id="synthetic-session",
            interface="eth0",
            source_ip="192.0.2.10",
            duration=2,
            heartbeat_seconds=1,
            startup_timeout=5,
            output=output,
            process_probe=probe,
            popen_factory=popen,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
            now=clock.now,
            stop_requested=stop_requested,
            stop_group=stop,
        )
        return report, clock, stopped

    def test_normal_capture_runs_full_duration_after_ready(self):
        report, clock, stopped = self.run_fake()
        self.assertEqual(report["termination_reason"], "duration_elapsed")
        self.assertTrue(report["session_basic_checks_passed"])
        self.assertEqual(report["effective_duration_seconds"], 2)
        self.assertEqual(report["process_monitoring"]["tcpdump_observations_missing"], 0)
        self.assertTrue(stopped["value"])

    def test_delayed_readiness_does_not_consume_effective_duration(self):
        report, _clock, _stopped = self.run_fake(delayed=True)
        self.assertEqual(report["started_at"], "2026-10-27T00:00:00Z")
        self.assertEqual(report["capture_effective_started_at"], "2026-10-27T00:00:02Z")
        self.assertEqual(report["effective_duration_seconds"], 2)
        self.assertEqual(report["capture_effective_ended_at"], "2026-10-27T00:00:04Z")
        self.assertEqual(report["finished_at"], "2026-10-27T00:00:08Z")
        self.assertEqual(report["termination_reason"], "duration_elapsed")

    def test_interruption_is_recorded_and_never_passes_basic_gate(self):
        report, _clock, _stopped = self.run_fake(interrupt=True)
        self.assertEqual(report["termination_reason"], "interrupted")
        self.assertEqual(report["interruption"]["signal"], "SIGTERM")
        self.assertFalse(report["session_basic_checks_passed"])
        self.assertFalse(report["collection_complete"])


if __name__ == "__main__":
    unittest.main()
