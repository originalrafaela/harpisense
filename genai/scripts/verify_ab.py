"""At most two synthetic real generations via loopback service and adapter.

Exit success means provenance/transport only, never semantic quality approval.
"""
import hashlib
import json
from pathlib import Path
import threading
import time

from genai.harpia.client import Client
from genai.harpia.contracts import CHAT_TEMPLATE, SYSTEM
from genai.harpia.memory import MemoryPolicy, available_memory, process_memory
from genai.harpia.runtime import Runtime
from genai.harpia.server import LocalServer


CASES = [
    {"incident_id": "synthetic-economic-A", "revision": 1, "facts": {
        "asset_id": "poste-2", "status": "OBSERVED",
        "evidence_summary": ["Poste 2 sem comunicação; sem evidência de ataque."],
        "limitations": ["Caso sintético. Causa desconhecida.", "Sem evidência de defesa executada."],
        "rf_attack_probability": None, "if_anomaly_score": None,
        "risk_score": None, "decision_status": None, "execution_status": None}},
    {"incident_id": "synthetic-economic-B", "revision": 1, "facts": {
        "status": "OBSERVED", "rf_attack_probability": 0.82, "rf_calibrated": True,
        "if_anomaly_score": 0.12,
        "if_score_meaning": "Score operacional; maior significa mais anômalo, não probabilidade.",
        "risk_status": "INCOMPLETE", "risk_score": None, "risk_level": None,
        "risk_factors": ["detection=null", "corroboration=null", "impact=null", "anomaly=null", "criticality=null"],
        "decision_status": "OBSERVE_ONLY", "decision_action": None,
        "execution_status": None, "execution_enabled": False,
        "limitations": ["Caso sintético; snapshot sem fatores suficientes para concluir risco.",
                        "Nenhuma execução registrada; observar é a decisão fornecida, não gerada pelo BitNet."]}},
]


class RecordedRuntime(Runtime):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.generations = []

    def complete(self, text, tokens):
        record = {"prompt": text, "budget": self.last_budget, "memory_before": available_memory()}
        started = time.monotonic()
        try:
            answer = super().complete(text, tokens)
            record.update(text=answer, text_sha256=hashlib.sha256(answer.encode()).hexdigest(),
                          source="model", memory_after=available_memory(),
                          process_memory=process_memory(self.process))
            return answer
        except Exception as exc:
            record.update(error=type(exc).__name__, runtime_error=self.error)
            raise
        finally:
            record["seconds"] = time.monotonic() - started
            self.generations.append(record)


def main():
    config = json.loads(Path('genai/config.example.json').read_text())
    folder = Path('.local-harpia/results')
    folder.mkdir(parents=True, exist_ok=True)
    runtime = RecordedRuntime(config['runtime_url'], config['inference_timeout_seconds'],
                              MemoryPolicy(**config['memory_policy']), config['output_tokens'])
    report = {"kind": "synthetic_real_AB", "memory_before": available_memory(),
              "template": CHAT_TEMPLATE, "system": SYSTEM, "config": config,
              "sampling": {"temperature": 0, "seed": 42, "gpu_layers": 0,
                           "stop": ["<|eot_id|>", "<|end_of_text|>"]},
              "inference_executed": False, "cases": [], "quality": "manual_review_required"}
    server = thread = None
    try:
        # Check the admission policy before reading all weights or starting any process.
        reason = runtime.memory_policy.entry_reason(report['memory_before'])
        if reason:
            report['blocked_reason'] = reason
            return 2
        model = Path(config['model_path'])
        with model.open('rb') as weights:
            digest = hashlib.file_digest(weights, 'sha256').hexdigest()
        report['model_sha256'] = digest
        if digest != json.loads(Path('genai/artifacts.lock.json').read_text())['model']['sha256']:
            report['blocked_reason'] = 'model_integrity_mismatch'
            return 2
        if not runtime.start(config['runtime_executable'], model, config['logs_dir'],
                             config['threads'], config['context_tokens']):
            report['blocked_reason'] = runtime.error
            return 2
        report['load_seconds'] = runtime.load_seconds
        server = LocalServer(('127.0.0.1', 0), runtime, max_waiting=config['max_waiting'],
                             queue_wait_seconds=config['queue_wait_seconds'])
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.02})
        thread.start()
        client = Client(f'http://127.0.0.1:{server.server_port}', token='', timeout=60)
        for context in CASES:
            started = time.monotonic()
            before = len(runtime.generations)
            result = client.explanation(context)
            generated = runtime.generations[before:]
            proof = (result['source'] == 'bitnet_unverified_text' and len(generated) == 1
                     and generated[0].get('text') == result['text'])
            report['cases'].append({'input': context, 'output': result,
                                    'seconds': time.monotonic() - started,
                                    'matches_real_generation': proof})
            report['inference_executed'] |= proof
            if runtime.failed:
                break
        return 0 if len(report['cases']) == 2 and all(c['matches_real_generation'] for c in report['cases']) else 1
    except Exception as exc:
        report['error'] = type(exc).__name__
        return 1
    finally:
        if server:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        process = runtime.process
        runtime.stop()
        report['runtime_stopped'] = process is None or process.poll() is not None
        report['generations'] = runtime.generations
        report['memory_samples'] = list(runtime.memory_samples)
        report['runtime_error'] = runtime.error
        (folder / 'economic-ab.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        # Full synthetic evidence is local; compact console output avoids native banners.
        print(json.dumps({k: v for k, v in report.items() if k not in
                          {'system', 'template', 'config', 'memory_samples', 'generations'}},
                         ensure_ascii=True, indent=2))


if __name__ == '__main__':
    raise SystemExit(main())
