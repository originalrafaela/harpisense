"""Unit/HTTP checks for the experimental P11-selected-facts path; no real model."""
import unittest

from genai.harpia.client import Client
from genai.harpia.contracts import ModelOutputRejected, context_dto, prompt, valid_model_text
from genai.harpia.server import LocalServer
from genai.scripts.verify_fidelity import (EVALUATION_CASES, MALICIOUS_MARKER,
                                           make_context, used_generation_budget)


class StaticRuntime:
    def ready(self):
        return True

    def complete(self, _text, _tokens):
        return '{"facts": null}'


class FidelityTests(unittest.TestCase):
    def test_lost_output_attempt_reserves_bounded_generation_budget(self):
        self.assertEqual(used_generation_budget({
            "budget_reserve_generations": 2,
            "cases": [{"generation_count": 1}],
        }), 3)

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

    def test_missing_results_case_contains_only_representable_unknowns(self):
        case = next(item for item in EVALUATION_CASES if item["id"] == "eval-missing-results")
        _store, context = make_context(case)
        facts = context["facts"]
        self.assertEqual(facts["status"], "OBSERVED")
        self.assertEqual(facts["risk_status"], "NOT_EVALUATED")
        self.assertIsNone(facts["rf_attack_probability"])
        self.assertIsNone(facts["if_anomaly_score"])
        self.assertIsNone(facts["execution_status"])
        self.assertIsNone(facts["evidence_summary"])

    def test_selected_p11_xai_contribution_is_preserved_for_prompt(self):
        case = next(item for item in EVALUATION_CASES if item["id"] == "eval-rf-if-risk")
        _store, context = make_context(case)
        self.assertEqual(context["facts"]["xai_contributions"], [
            {"feature": "packet_count", "value": 140.0, "contribution": 0.045},
        ])
        self.assertIn('"contribution": 0.045', prompt(context))

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
