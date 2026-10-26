import unittest

from context_adapter import attach_context


EVENT = {
    "evidence_id": "e1",
    "event_type": "mqtt_auth_failure",
    "observed_at": "2026-10-15T12:00:05Z",
    "coverage": "COMPLETE",
}

BINDING = {
    "evidence_id": "e1",
    "collection_session_id": "session-A",
    "sensor_id": "sensor-A",
    "target_ref": "device-A",
}


class TestContextAdapter(unittest.TestCase):

    def test_valid_binding(self):
        result = attach_context([EVENT], [BINDING])
        self.assertEqual(result[0]["target_ref"], "device-A")

    def test_missing_binding(self):
        with self.assertRaises(ValueError):
            attach_context([EVENT], [])

    def test_ambiguous_binding(self):
        with self.assertRaises(ValueError):
            attach_context([EVENT], [BINDING, dict(BINDING)])

    def test_missing_context(self):
        binding = dict(BINDING)
        del binding["sensor_id"]

        with self.assertRaises(ValueError):
            attach_context([EVENT], [binding])

    def test_original_evidence_unchanged(self):
        attach_context([EVENT], [BINDING])
        self.assertNotIn("target_ref", EVENT)

    def test_reserved_context_rejected(self):
        event = {**EVENT, "sensor_id": "untrusted"}

        with self.assertRaises(ValueError):
            attach_context([event], [BINDING])

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            attach_context({}, [])


if __name__ == "__main__":
    unittest.main()
