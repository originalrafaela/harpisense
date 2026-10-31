"""Input contract tests plus opt-in, isolated PostgreSQL acceptance tests."""
import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import Mock
from uuid import uuid4

from delivery.mqtt_input import (POSTE1_DEVICE, POSTE1_TOPIC, POSTE2_TOPIC,
                                 TelemetryInput)


def sample(sequence=0, boot="0123456789abcdef"):
    return dict(schema_version="harpisense.telemetry.candidate.v2",
                device_id=POSTE1_DEVICE, sensor_type="ldr", sequence=sequence,
                message_id=f"{POSTE1_DEVICE}-{boot}-{sequence}",
                observed_at="2026-10-31T12:00:00Z",
                measurements=dict(ldr_adc_raw=2048, led_commanded_on=True),
                status=dict(origin_type="PHYSICAL", reading_unit="adc_raw",
                            reading_quality="RAW_UNCALIBRATED"))


def wire(data):
    return json.dumps(data, separators=(",", ":")).encode()


class InputTests(unittest.TestCase):
    def setUp(self):
        self.store, self.audit = Mock(), Mock()
        self.store.insert.return_value = True
        self.adapter = TelemetryInput(self.store, self.audit, poste1_enabled=True)

    def test_default_flag_subscriptions_and_callback(self):
        closed = TelemetryInput(self.store, self.audit)
        client = Mock()
        closed.subscribe(client)
        client.subscribe.assert_called_once_with(POSTE2_TOPIC, qos=1)
        self.assertEqual(closed.handle(POSTE1_TOPIC, wire(sample())), "disabled")
        self.store.insert.assert_not_called()
        self.adapter.subscribe(client)
        client.subscribe.assert_any_call(POSTE1_TOPIC, qos=1)
        self.assertEqual(self.adapter.on_message(None, None, Mock(topic=POSTE1_TOPIC,
                         payload=wire(sample()))), "inserted")
        with self.assertRaises(TypeError):
            TelemetryInput(self.store, self.audit, poste1_enabled="false")

    def test_valid_boundaries_quality_and_old_out_of_order_times(self):
        for adc, quality in [(0, "RAW_UNCALIBRATED"), (4095, "RAW_UNCALIBRATED"),
                             (None, "UNAVAILABLE"), (None, "OUT_OF_RANGE")]:
            data = sample(9007199254740991)
            data["observed_at"] = "2001-01-01T01:02:03.123Z"
            data["measurements"]["ldr_adc_raw"] = adc
            data["status"]["reading_quality"] = quality
            self.assertEqual(self.adapter.handle(POSTE1_TOPIC, wire(data)), "inserted")
            kind, record = self.store.insert.call_args.args
            self.assertEqual(kind, "telemetry")
            self.assertEqual(record.data, data)
            self.assertEqual(record.revision, 1)
            self.assertEqual(record.source, "trusted-service")
            self.assertEqual(record.id, "poste1-" + hashlib.sha256(
                POSTE1_DEVICE.encode() + b"\0" + data["message_id"].encode()).hexdigest())
            self.assertNotIn("received_at", record.data)

    def test_invalid_profile_fields_types_and_limits(self):
        cases = [({"device_id": "poste2"}), {"sensor_type": "temperature"},
                 {"schema_version": "1"}, {"sequence": True}, {"sequence": 1.0},
                 {"sequence": -1}, {"sequence": 9007199254740992},
                 {"message_id": "arbitrary"}, {"message_id": "x" * 65},
                 {"observed_at": "1970-01-01"}, {"observed_at": "2026-02-30T00:00:00Z"},
                 {"observed_at": "2026-10-31T12:00:00+00:00"},
                 {"observed_at": "2026-10-31T12:00:00-03:00"},
                 {"extra": 1}]
        for update in cases:
            data = sample()
            data.update(update)
            self.assertEqual(self.adapter.handle(POSTE1_TOPIC, wire(data)), "invalid", update)
        for field, values in [("ldr_adc_raw", [-1, 4096, True, 1.0, "1", None]),
                              ("led_commanded_on", [0, 1, "true", None])]:
            for value in values:
                data = sample()
                data["measurements"][field] = value
                self.assertEqual(self.adapter.handle(POSTE1_TOPIC, wire(data)), "invalid")
        for update in [{"origin_type": "SIMULATED"}, {"reading_unit": "lux"},
                       {"reading_quality": "UNAVAILABLE"}, {"calibration_version": None},
                       {"extra": 1}]:
            data = sample()
            data["status"].update(update)
            self.assertEqual(self.adapter.handle(POSTE1_TOPIC, wire(data)), "invalid")
        data = sample()
        data["measurements"]["lux"] = 1
        self.assertEqual(self.adapter.handle(POSTE1_TOPIC, wire(data)), "invalid")
        for field in sample():
            data = sample()
            del data[field]
            self.assertEqual(self.adapter.handle(POSTE1_TOPIC, wire(data)), "invalid")
        self.store.insert.assert_not_called()

    def test_strict_json_and_received_byte_limit(self):
        raw = wire(sample())
        invalid = [b"\xff", b"[]", b"null", b"{", b"\xef\xbb\xbf" + raw,
                   raw[:-1] + b',"sequence":0}',
                   raw.replace(b'"ldr_adc_raw":2048', b'"ldr_adc_raw":2048,"ldr_adc_raw":2048'),
                   raw.replace(b"2048", b"NaN"), raw.replace(b"2048", b"Infinity"),
                   raw + b" " * (1025 - len(raw))]
        for value in invalid:
            self.assertEqual(self.adapter.handle(POSTE1_TOPIC, value), "invalid")
        self.store.insert.assert_not_called()
        self.assertEqual(self.adapter.handle(POSTE1_TOPIC, raw + b" " * (1024-len(raw))), "inserted")

    def test_topic_identity_dispatch_and_poste2_byte_regression(self):
        for topic, data in [(POSTE1_TOPIC, {"device_id": "poste2"}),
                            (POSTE2_TOPIC, sample()), (POSTE1_TOPIC + "/other", sample())]:
            self.assertEqual(self.adapter.handle(topic, wire(data)), "invalid")
        self.store.insert.assert_not_called()
        ids = []
        for raw in [b'{"device_id":"poste2","timestamp":"old","temperature":12}',
                    b'{ "device_id": "poste2", "timestamp": "old", "temperature": 12 }']:
            self.assertEqual(self.adapter.handle(POSTE2_TOPIC, raw), "inserted")
            record = self.store.insert.call_args.args[1]
            self.assertEqual(record.data, json.loads(raw))
            self.assertEqual(record.id, "poste2-" + hashlib.sha256(POSTE2_TOPIC.encode()+b"\0"+raw).hexdigest())
            ids.append(record.id)
        self.assertNotEqual(*ids)

    def test_duplicate_conflict_and_operational_error_are_distinct(self):
        self.store.insert.return_value = False
        self.assertEqual(self.adapter.handle(POSTE1_TOPIC, wire(sample())), "duplicate")
        self.audit.assert_called_with("duplicate_message")
        self.store.insert.side_effect = ValueError("immutable revision conflict")
        self.assertEqual(self.adapter.handle(POSTE1_TOPIC, wire(sample())), "identifier_conflict")
        self.audit.assert_called_with("identifier_conflict")
        for exc in [ValueError("invalid record"), RuntimeError("database offline")]:
            self.store.insert.side_effect = exc
            with self.assertRaises(type(exc)):
                self.adapter.handle(POSTE1_TOPIC, wire(sample()))


@unittest.skipUnless(os.getenv("HARPISENSE_POSTE1_TEST_DSN"), "isolated PostgreSQL required")
class PostgreSQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        from delivery.postgres_store import PostgresStore
        cls.store = PostgresStore(os.environ["HARPISENSE_POSTE1_TEST_DSN"])
        with cls.store._connect() as conn:
            if conn.execute("SELECT current_database()").fetchone()[0] != "poste1_fixture":
                raise RuntimeError("Only disposable poste1_fixture is allowed")
            conn.execute((Path(__file__).parents[1] / "delivery/001_local.sql").read_text())

    def setUp(self):
        self.data = sample(boot=uuid4().hex[:16])
        self.adapter = TelemetryInput(self.store, lambda event: None, poste1_enabled=True)

    def test_persistent_retry_conflict_timestamp_and_no_revision_two(self):
        raw = wire(self.data)
        self.assertEqual(self.adapter.handle(POSTE1_TOPIC, raw), "inserted")
        record_id = "poste1-" + hashlib.sha256(POSTE1_DEVICE.encode()+b"\0"+self.data["message_id"].encode()).hexdigest()
        with self.store._connect() as conn:
            original_created = conn.execute("SELECT created_at FROM projections WHERE id=%s", (record_id,)).fetchone()[0]
        self.assertEqual(self.adapter.handle(POSTE1_TOPIC, json.dumps(self.data, indent=2).encode()), "duplicate")
        changed = copy.deepcopy(self.data)
        changed["measurements"]["led_commanded_on"] = False
        self.assertEqual(self.adapter.handle(POSTE1_TOPIC, wire(changed)), "identifier_conflict")
        record_id = "poste1-" + hashlib.sha256(POSTE1_DEVICE.encode()+b"\0"+self.data["message_id"].encode()).hexdigest()
        self.assertEqual(self.store.history("telemetry", record_id),
                         [dict(revision=1, source="trusted-service", data=self.data)])
        with self.store._connect() as conn:
            data, created = conn.execute("SELECT data, created_at FROM projections WHERE id=%s", (record_id,)).fetchone()
        self.assertEqual(data["observed_at"], self.data["observed_at"])
        self.assertEqual(created, original_created)
        self.assertGreater(created.year, 2000)

    def test_delayed_out_of_order_and_invalid_never_change_stored_samples(self):
        newer = copy.deepcopy(self.data)
        newer["observed_at"] = "2026-10-31T13:00:00Z"
        older = copy.deepcopy(self.data)
        older["sequence"] = 1
        older["message_id"] = older["message_id"][:-1] + "1"
        older["observed_at"] = "2001-01-01T00:00:00Z"
        self.assertEqual(self.adapter.handle(POSTE1_TOPIC, wire(newer)), "inserted")
        self.assertEqual(self.adapter.handle(POSTE1_TOPIC, wire(older)), "inserted")
        older["device_id"] = "poste2"
        self.assertEqual(self.adapter.handle(POSTE1_TOPIC, wire(older)), "invalid")
        with self.store._connect() as conn:
            rows = conn.execute("SELECT data->>'observed_at' FROM projections WHERE data->>'message_id' IN (%s,%s)",
                                (newer["message_id"], older["message_id"])).fetchall()
        self.assertEqual(sorted(row[0] for row in rows),
                         ["2001-01-01T00:00:00Z", "2026-10-31T13:00:00Z"])

    def test_simultaneous_duplicates_and_conflicting_ids(self):
        def concurrent(payloads):
            barrier = threading.Barrier(2)
            def send(data):
                barrier.wait()
                return self.adapter.handle(POSTE1_TOPIC, wire(data))
            with ThreadPoolExecutor(2) as pool:
                return sorted(pool.map(send, payloads))
        self.assertEqual(concurrent([self.data, self.data]), ["duplicate", "inserted"])
        self.data = sample(boot=uuid4().hex[:16])
        changed = copy.deepcopy(self.data)
        changed["measurements"]["ldr_adc_raw"] = 1
        self.assertEqual(concurrent([self.data, changed]), ["identifier_conflict", "inserted"])

    def test_poste2_raw_whitespace_remains_separate_and_retry_duplicates(self):
        data = {"device_id": "poste2", "test_id": uuid4().hex}
        for raw in [wire(data), json.dumps(data, indent=2).encode()]:
            self.assertEqual(self.adapter.handle(POSTE2_TOPIC, raw), "inserted")
            self.assertEqual(self.adapter.handle(POSTE2_TOPIC, raw), "duplicate")
            record_id = "poste2-" + hashlib.sha256(POSTE2_TOPIC.encode()+b"\0"+raw).hexdigest()
            self.assertEqual(self.store.history("telemetry", record_id)[0]["data"], data)


if __name__ == "__main__":
    unittest.main()
