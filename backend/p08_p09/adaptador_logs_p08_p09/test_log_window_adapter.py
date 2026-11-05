import unittest

from log_window_adapter import prepare_log_counts, parse_timestamp


WINDOW = {
    "collection_session_id": "session-A",
    "sensor_id": "sensor-A",
    "target_ref": "device-A",
    "window_id": "w1",
    "window_start": "2026-10-15T12:00:00Z",
    "window_end": "2026-10-15T12:00:10Z",
}


def event(uid="e1", timestamp="2026-10-15T12:00:05Z",
          kind="mqtt_auth_failure", coverage="COMPLETE"):
    return {
        "collection_session_id": "session-A",
        "sensor_id": "sensor-A",
        "target_ref": "device-A",
        "evidence_id": uid,
        "observed_at": timestamp,
        "event_type": kind,
        "coverage": coverage,
    }


class TestLogWindowAdapter(unittest.TestCase):

    def test_count(self):
        result = prepare_log_counts([event()], [WINDOW])
        self.assertEqual(result["w1"]["auth_failures"], 1)

    def test_duplicate(self):
        result = prepare_log_counts([event(), event()], [WINDOW])
        self.assertEqual(result["w1"]["auth_failures"], 1)

    def test_incomplete_coverage(self):
        result = prepare_log_counts(
            [event(coverage="PARTIAL")], [WINDOW]
        )
        self.assertEqual(result["w1"], {})

    def test_start_inclusive(self):
        result = prepare_log_counts(
            [event(timestamp="2026-10-15T12:00:00Z")], [WINDOW]
        )
        self.assertEqual(result["w1"]["auth_failures"], 1)

    def test_end_exclusive(self):
        result = prepare_log_counts(
            [event(timestamp="2026-10-15T12:00:10Z")], [WINDOW]
        )
        self.assertEqual(result["w1"], {})

    def test_unknown_event(self):
        result = prepare_log_counts(
            [event(kind="unknown")], [WINDOW]
        )
        self.assertEqual(result["w1"], {})

    def test_invalid_window(self):
        invalid = dict(WINDOW)
        invalid["window_end"] = invalid["window_start"]

        with self.assertRaises(ValueError):
            prepare_log_counts([], [invalid])

    def test_timestamp_without_timezone(self):
        with self.assertRaises(ValueError):
            parse_timestamp("2026-10-15T12:00:00")

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            prepare_log_counts({}, [])

    def test_multiple_features(self):
        result = prepare_log_counts(
            [
                event("e1", kind="mqtt_auth_failure"),
                event("e2", kind="mqtt_acl_denial"),
            ],
            [WINDOW],
        )
        self.assertEqual(result["w1"]["auth_failures"], 1)
        self.assertEqual(result["w1"]["mqtt_acl_denials"], 1)


if __name__ == "__main__":
    unittest.main()


class TestContextIsolation(unittest.TestCase):

    def test_different_session_must_not_count(self):
        window = {
            **WINDOW,
            "collection_session_id": "session-A",
        }

        evidence = {
            **event(),
            "collection_session_id": "session-B",
        }

        result = prepare_log_counts([evidence], [window])

        self.assertEqual(
            result["w1"],
            {},
            "Evidência de outra sessão não pode ser contabilizada",
        )


class TestAdditionalIsolation(unittest.TestCase):

    def test_different_sensor(self):
        evidence = {**event(), "sensor_id": "sensor-B"}
        result = prepare_log_counts([evidence], [WINDOW])
        self.assertEqual(result["w1"], {})

    def test_different_target(self):
        evidence = {**event(), "target_ref": "device-B"}
        result = prepare_log_counts([evidence], [WINDOW])
        self.assertEqual(result["w1"], {})

    def test_missing_context(self):
        evidence = event()
        del evidence["collection_session_id"]
        result = prepare_log_counts([evidence], [WINDOW])
        self.assertEqual(result["w1"], {})

    def test_duplicate_window_id(self):
        with self.assertRaises(ValueError):
            prepare_log_counts([], [WINDOW, dict(WINDOW)])
