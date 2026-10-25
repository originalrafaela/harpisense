"""Opt-in comparison adapter: Qwen3 ChatML, official non-thinking prefill.

No automatic selection or replacement of the BitNet profile.
"""
from .contracts import SYSTEM
from .runtime import Runtime


def qwen_frame(data):
    return ('<|im_start|>system\n' + SYSTEM + '<|im_end|>\n'
            + '<|im_start|>user\n' + data.strip() + '<|im_end|>\n'
            + '<|im_start|>assistant\n<think>\n\n</think>\n\n')


class QwenRuntime(Runtime):
    model_id = 'Qwen3-0.6B-Q4_K_M'
    text_source = 'model_unverified_text'

    def frame_data(self, data):
        return qwen_frame(data)

    def _completion_payload(self, text, tokens):
        return {"prompt": text, "n_predict": tokens, "temperature": 0.7,
                "top_p": 0.8, "top_k": 20, "min_p": 0.0,
                "seed": 42, "stream": False, "cache_prompt": True, "n_keep": 0,
                "stop": ['<|im_end|>', '<|endoftext|>']}
