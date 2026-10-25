"""Transport/framing tests only; these do not approve model semantic fidelity."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from genai.harpia.client import Client
from genai.harpia.contracts import SYSTEM, context_dto, prepare_prompt, prompt
from genai.harpia.qwen import QwenRuntime, qwen_frame
from genai.harpia.runtime import Runtime


class ComparisonTests(unittest.TestCase):
    def test_qwen_non_thinking_frame_has_single_system_user_and_empty_prefill(self):
        text = qwen_frame('dados')
        self.assertEqual(text.count('<|im_start|>system'), 1)
        self.assertEqual(text.count('<|im_start|>user'), 1)
        self.assertEqual(text.count('<|im_start|>assistant'), 1)
        self.assertIn(SYSTEM, text)
        self.assertTrue(text.endswith('<|im_start|>assistant\n<think>\n\n</think>\n\n'))
        self.assertNotIn('System:', text)
        self.assertNotIn('<|eot_id|>', text)

    def test_same_dto_values_and_injection_neutralization_for_both_frames(self):
        cases = json.loads(Path('genai/comparison_cases.json').read_text(encoding='utf-8'))
        for case in cases:
            if 'context' not in case:
                continue
            safe = context_dto(case['context'])
            qwen, budget = prepare_prompt(safe, lambda _: 200, 1024, 96, qwen_frame)
            bitnet = prompt(safe)
            expected = json.dumps(safe, ensure_ascii=False, sort_keys=True)
            self.assertIn(expected, qwen)
            self.assertIn(expected, bitnet)
            self.assertEqual(budget['omitted_fields'], [])
        attack = cases[-1]['context']
        text, _ = prepare_prompt(attack, lambda _: 200, 1024, 96, qwen_frame)
        self.assertEqual(text.count('<|im_start|>system'), 1)
        self.assertIn('＜｜im_start｜＞system', text)
        self.assertIn('Ignore as regras', text)  # quoted untrusted data, never promoted to a role

    def test_payload_sampling_and_stops_are_model_specific(self):
        bitnet = Runtime()._completion_payload('dados', 96)
        qwen = QwenRuntime()._completion_payload('dados', 96)
        self.assertEqual(bitnet['temperature'], 0)
        self.assertEqual(qwen['temperature'], 0.7)
        self.assertEqual((qwen['top_p'], qwen['top_k'], qwen['min_p']), (0.8, 20, 0))
        self.assertEqual(qwen['stop'], ['<|im_end|>', '<|endoftext|>'])
        self.assertEqual(qwen['n_predict'], bitnet['n_predict'])
        self.assertNotIn('grammar', qwen)

    def test_opt_in_model_identity_and_source_are_required(self):
        context = {'incident_id': 'synthetic-test', 'revision': 1, 'facts': {}}
        result = {**context, 'source': 'model_unverified_text', 'model_id': QwenRuntime.model_id,
                  'text': 'Resposta SIMULADA.', 'bitnet_status': 'responded_unverified'}
        explicit = Client(expected_model=QwenRuntime.model_id, expected_source='model_unverified_text',
                          transport=lambda *_: result)
        self.assertEqual(explicit.explanation(context)['model_id'], QwenRuntime.model_id)
        self.assertEqual(Client(transport=lambda *_: result).explanation(context)['source'], 'deterministic_fallback')
        wrong = Client(expected_model='wrong', expected_source='model_unverified_text', transport=lambda *_: result)
        self.assertEqual(wrong.explanation(context)['source'], 'deterministic_fallback')
        with self.assertRaises(ValueError):
            Client(expected_source='model_unverified_text')
        with self.assertRaises(ValueError):
            Client(expected_model=['untrusted'], expected_source='model_unverified_text')

    def test_default_bitnet_frame_is_unchanged(self):
        runtime = Runtime()
        context = {'incident_id': 'synthetic-test', 'revision': 1, 'facts': {}}
        with patch.object(runtime, 'count_tokens', return_value=100):
            self.assertEqual(runtime.prepare_context(context, 96), prompt(context))


if __name__ == '__main__':
    unittest.main()
