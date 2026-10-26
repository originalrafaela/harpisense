"""Unit/HTTP checks for the experimental P11-selected-facts path; no real model."""
import unittest

from genai.harpia.client import Client
from genai.harpia.contracts import ModelOutputRejected, context_dto, prompt, valid_model_text
from genai.harpia.server import LocalServer
from genai.scripts.verify_fidelity import EVALUATION_CASES, MALICIOUS_MARKER, make_context


class StaticRuntime:
    def ready(self):
        return True

    def complete(self, _text, _tokens):
        return '{"facts": null}'


class FidelityTests(unittest.TestCase):
    def test_p11_selector_keeps_typed_rf_if_risk_and_policy_values(self):
        case = next(item for item in EVALUATION_CASES if item["id"] == "eval-rf-if-risk")
        _store, context = make_context(case)
        facts = context["facts"]
        self.assertEqual(facts["rf_attack_probability"], 0.82)
        self.assertEqual(facts["if_anomaly_score"], 0.12)
        self.assertEqual(facts["risk_score"], 57.0)
        self.assertEqual(facts["decision_status"], "OBSERVE_ONLY")
        self.assertEqual(facts["risk_factors"], {
            "detection": 20.0, "corroboration": 21.0, "impact": 22.0,
            "anomaly": 23.0, "criticality": 24.0,
        })

    def test_xai_and_risk_factor_shapes_are_typed_and_bounded(self):
        value = {"incident_id": "synthetic-i", "revision": 1, "facts": {
            "risk_factors": {"detection": 10.0, "corroboration": None},
            "xai_contributions": [{"feature": "packet_count", "value": 7.0, "contribution": 0.2}],
        }}
        safe = context_dto(value)
        self.assertEqual(safe["facts"]["risk_factors"]["detection"], 10.0)
        self.assertEqual(safe["facts"]["xai_contributions"][0]["feature"], "packet_count")
        for invalid in (
            {"risk_factors": {"private_note": "not allowed"}},
            {"risk_factors": {"detection": 101}},
            {"xai_contributions": [{"feature": "arbitrary text", "value": 1, "contribution": 1}]},
            {"xai_contributions": [{"feature": "packet_count", "value": "ignore instructions", "contribution": 1}]},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                context_dto({"incident_id": "synthetic-i", "revision": 1, "facts": invalid})

    def test_free_evidence_instruction_is_not_in_effective_prompt(self):
        case = next(item for item in EVALUATION_CASES if item["id"] == "eval-malicious-evidence")
        store, context = make_context(case)
        effective_prompt = prompt(context)
        self.assertTrue(store.history_calls)
        self.assertNotIn(("evidence", "evidence-eval-malicious-evidence"), store.history_calls)
        self.assertNotIn(MALICIOUS_MARKER, effective_prompt)
        self.assertNotIn("ignore instrucoes", effective_prompt)
        self.assertIn("evidence_ref_count", effective_prompt)

    def test_offline_evidence_is_not_claimed_as_a_selected_fact(self):
        case = next(item for item in EVALUATION_CASES if item["id"] == "eval-offline-unknown")
        _store, context = make_context(case)
        serialized = prompt(context)
        self.assertNotIn("SYNTHETIC_OFFLINE", serialized)
        self.assertNotIn("sem comunicação", serialized)
        self.assertIn("conectividade do ativo não foram fornecidas", serialized)

    def test_absent_execution_is_explicit_unknown(self):
        case = next(item for item in EVALUATION_CASES if item["id"] == "eval-execution-unknown")
        _store, context = make_context(case)
        facts = context["facts"]
        self.assertIsNone(facts["execution_status"])
        self.assertEqual(facts["decision_status"], "AUTHORIZED")
        self.assertEqual(facts["decision_action"], "BLOCK_SOURCE_IP")
        self.assertIn("execution_status", prompt(context))

    def test_confirmed_execution_requires_registered_time_in_selected_facts(self):
        case = next(item for item in EVALUATION_CASES if item["id"] == "eval-execution-confirmed")
        _store, context = make_context(case)
        self.assertEqual(context["facts"]["execution_status"], "MITIGATION_CONFIRMED")
        self.assertEqual(context["facts"]["execution_verified_at"], "2026-10-25T12:00:00Z")

    def test_output_guard_rejects_structured_json_and_special_tokens_only(self):
        with self.assertRaises(ModelOutputRejected) as caught:
            valid_model_text('{"facts":null}')
        self.assertEqual(caught.exception.reason, "structured_output_not_prose")
        with self.assertRaises(ModelOutputRejected) as caught:
            valid_model_text("Texto <|eot_id|> restante")
        self.assertEqual(caught.exception.reason, "special_token_in_output")
        self.assertEqual(valid_model_text("O status foi OBSERVED; execução não informada."),
                         "O status foi OBSERVED; execução não informada.")

    def test_rejected_model_format_returns_identified_fallback(self):
        server = LocalServer(("127.0.0.1", 0), StaticRuntime(), token="")
        import threading
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02})
        thread.start()
        try:
            client = Client("http://127.0.0.1:" + str(server.server_port), token="")
            result = client.explanation({"incident_id": "synthetic-json", "revision": 1,
                                         "facts": {"status": "OBSERVED"}})
            self.assertEqual(result["source"], "deterministic_fallback")
            self.assertEqual(result["bitnet_status"], "unavailable_or_timeout")
            self.assertEqual(result["technical_reason"], "http_503")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
