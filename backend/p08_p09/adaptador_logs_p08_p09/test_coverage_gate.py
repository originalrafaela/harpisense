import unittest

from coverage_gate import validate_coverage


class TestCoverageGate(unittest.TestCase):

    def test_missing_coverage_rejected(self):
        reasons = validate_coverage(
            window_start="2026-10-15T12:00:00Z",
            window_end="2026-10-15T12:00:10Z",
            coverage_records=[],
            required_sources=("mosquitto",),
            collection_session_id="session-A",
            sensor_id="sensor-A",
            target_ref="device-A",
        )
        self.assertTrue(reasons)

    def test_partial_coverage_rejected(self):
        records = [{
            "source": "mosquitto",
            "start": "2026-10-15T12:00:02Z",
            "end": "2026-10-15T12:00:10Z",
            "verified": True,
            "collection_session_id": "session-A",
            "sensor_id": "sensor-A",
            "target_ref": "device-A",
        }]
        reasons = validate_coverage(
            window_start="2026-10-15T12:00:00Z",
            window_end="2026-10-15T12:00:10Z",
            coverage_records=records,
            required_sources=("mosquitto",),
            collection_session_id="session-A",
            sensor_id="sensor-A",
            target_ref="device-A",
        )
        self.assertTrue(reasons)

    def test_unverified_coverage_rejected(self):
        records = [{
            "source": "mosquitto",
            "start": "2026-10-15T12:00:00Z",
            "end": "2026-10-15T12:00:10Z",
            "verified": False,
            "collection_session_id": "session-A",
            "sensor_id": "sensor-A",
            "target_ref": "device-A",
        }]
        reasons = validate_coverage(
            window_start="2026-10-15T12:00:00Z",
            window_end="2026-10-15T12:00:10Z",
            coverage_records=records,
            required_sources=("mosquitto",),
            collection_session_id="session-A",
            sensor_id="sensor-A",
            target_ref="device-A",
        )
        self.assertTrue(reasons)


if __name__ == "__main__":
    unittest.main()


class TestCoverageIntervals(unittest.TestCase):

    def check(self, records, sources=("mosquitto",)):
        return validate_coverage(
            window_start="2026-10-15T12:00:00Z",
            window_end="2026-10-15T12:00:10Z",
            coverage_records=records,
            required_sources=sources,
            collection_session_id="session-A",
            sensor_id="sensor-A",
            target_ref="device-A",
        )

    def record(self, source, start, end):
        return {
            "source": source,
            "start": f"2026-10-15T12:00:{start:02d}Z",
            "end": f"2026-10-15T12:00:{end:02d}Z",
            "verified": True,
            "collection_session_id": "session-A",
            "sensor_id": "sensor-A",
            "target_ref": "device-A",
        }

    def test_full_coverage_accepted(self):
        records = [self.record("mosquitto", 0, 10)]
        self.assertEqual(self.check(records), [])

    def test_consecutive_intervals_accepted(self):
        records = [
            self.record("mosquitto", 0, 5),
            self.record("mosquitto", 5, 10),
        ]
        self.assertEqual(self.check(records), [])

    def test_temporal_gap_rejected(self):
        records = [
            self.record("mosquitto", 0, 4),
            self.record("mosquitto", 5, 10),
        ]
        self.assertTrue(self.check(records))

    def test_missing_required_source_rejected(self):
        records = [self.record("mosquitto", 0, 10)]
        self.assertTrue(
            self.check(records, ("mosquitto", "fastapi"))
        )


class TestCoverageContext(unittest.TestCase):

    def test_different_session_rejected(self):
        records = [{
            "source": "mosquitto",
            "start": "2026-10-15T12:00:00Z",
            "end": "2026-10-15T12:00:10Z",
            "verified": True,
            "collection_session_id": "session-B",
            "sensor_id": "sensor-A",
            "target_ref": "device-A",
        }]

        reasons = validate_coverage(
            window_start="2026-10-15T12:00:00Z",
            window_end="2026-10-15T12:00:10Z",
            coverage_records=records,
            required_sources=("mosquitto",),
            collection_session_id="session-A",
            sensor_id="sensor-A",
            target_ref="device-A",
        )

        self.assertTrue(
            reasons,
            "Cobertura de outra sessão não pode ser aceita",
        )


class TestCoverageAdditionalContext(unittest.TestCase):

    def check(self, record, **overrides):
        context = {
            "collection_session_id": "session-A",
            "sensor_id": "sensor-A",
            "target_ref": "device-A",
        }
        context.update(overrides)

        return validate_coverage(
            window_start="2026-10-15T12:00:00Z",
            window_end="2026-10-15T12:00:10Z",
            coverage_records=[record],
            required_sources=("mosquitto",),
            **context,
        )

    def record(self):
        return {
            "source": "mosquitto",
            "start": "2026-10-15T12:00:00Z",
            "end": "2026-10-15T12:00:10Z",
            "verified": True,
            "collection_session_id": "session-A",
            "sensor_id": "sensor-A",
            "target_ref": "device-A",
        }

    def test_different_sensor_rejected(self):
        record = self.record()
        record["sensor_id"] = "sensor-B"
        self.assertTrue(self.check(record))

    def test_different_target_rejected(self):
        record = self.record()
        record["target_ref"] = "device-B"
        self.assertTrue(self.check(record))

    def test_missing_context_rejected(self):
        self.assertTrue(
            self.check(self.record(), sensor_id=None)
        )
