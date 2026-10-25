"""Four monitored synthetic generations; success proves transport, not quality."""
import copy
import hashlib
import json
from pathlib import Path
import threading
import time
import urllib.request
import argparse

from genai.harpia.client import Client, post_json
from genai.harpia.contracts import CHAT_TEMPLATE, SYSTEM, frame, valid_text
from genai.harpia.memory import MemoryPolicy, available_memory
from genai.harpia.server import LocalServer
from .verify_ab import CASES, RecordedRuntime

SIMPLE = 'Responda em português, em uma frase de texto, sem JSON: quanto é dois mais dois?'


class DiagnosticRuntime(RecordedRuntime):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.raw_completions = []

    def _observe_completion(self, payload, response):
        self.raw_completions.append({'request': payload, 'response': response})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--post-patch', action='store_true', help='Exactly simple + A/B, validating rebuilt executable hashes')
    args = parser.parse_args()
    config = json.loads(Path('genai/config.example.json').read_text())
    folder = Path('.local-harpia/results')
    folder.mkdir(parents=True, exist_ok=True)
    runtime = DiagnosticRuntime(config['runtime_url'], config['inference_timeout_seconds'],
                                MemoryPolicy(**config['memory_policy']), config['output_tokens'])
    report = {'kind': 'three_post_patch_synthetic_generations' if args.post_patch else 'four_synthetic_diagnostic_generations', 'memory_before': available_memory(),
              'config': config, 'system': SYSTEM, 'template': CHAT_TEMPLATE, 'cases': []}
    server = thread = None
    try:
        if args.post_patch:
            from .patch_runtime import PATCHED_SHA
            manifest = json.loads((folder / 'build-manifest.json').read_text())
            if manifest['source_sha256'] != PATCHED_SHA:
                raise ValueError('stale activation build manifest')
            for binary in manifest['binaries'].values():
                if hashlib.sha256(Path(binary['path']).read_bytes()).hexdigest() != binary['sha256']:
                    raise ValueError('binary does not match build manifest')
            if Path(manifest['binaries']['llama-server']['path']).resolve() != Path(config['runtime_executable']).resolve():
                raise ValueError('service executable differs from verified build')
            report['build_manifest'] = manifest
        reason = runtime.memory_policy.entry_reason(report['memory_before'])
        if reason:
            report['blocked_reason'] = reason
            return 2
        with Path(config['model_path']).open('rb') as weights:
            report['model_sha256'] = hashlib.file_digest(weights, 'sha256').hexdigest()
        if report['model_sha256'] != json.loads(Path('genai/artifacts.lock.json').read_text())['model']['sha256']:
            report['blocked_reason'] = 'model_integrity_mismatch'
            return 2
        if not runtime.start(config['runtime_executable'], config['model_path'], config['logs_dir'],
                             config['threads'], config['context_tokens']):
            report['blocked_reason'] = runtime.error
            return 2
        report['load_seconds'] = runtime.load_seconds
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(runtime.url + '/props', timeout=3) as response:
            report['runtime_properties'] = json.loads(response.read(65536))
        server = LocalServer(('127.0.0.1', 0), runtime)
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.02})
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        client = Client(base, token='', timeout=60)
        cases = copy.deepcopy(CASES)
        cases[0]['facts']['limitations'].append('Solicitação sintética: explique em texto corrido curto em português, sem JSON.')
        jobs = [('simple_direct', SIMPLE), ('simple_service_complete', SIMPLE),
                ('A_service_adapter', cases[0]), ('B_service_adapter', cases[1])]
        if args.post_patch:
            jobs = [jobs[0], jobs[2], jobs[3]]
        for name, supplied in jobs:
            runtime.last_budget = None
            before = len(runtime.generations)
            raw_before = len(runtime.raw_completions)
            start = time.monotonic()
            record = {'name': name, 'input': supplied}
            try:
                if name == 'simple_direct':
                    delivered = {'text': runtime.complete(frame(supplied), config['output_tokens']),
                                 'source': 'direct_runtime_not_adapter'}
                elif name == 'simple_service_complete':
                    delivered = post_json(base + '/complete', {'prompt': supplied,
                                          'max_tokens': config['output_tokens']}, 60)
                else:
                    delivered = client.explanation(supplied)
                generated = runtime.generations[before:]
                raw = runtime.raw_completions[raw_before:]
                record.update(delivered=delivered, generation=generated, raw=raw,
                              matches_real_generation=(len(raw) == 1 and
                                  delivered.get('text') == valid_text(raw[0]['response'].get('content'))))
            except Exception as exc:
                record.update(error=type(exc).__name__, runtime_error=runtime.error)
            record['seconds'] = time.monotonic() - start
            report['cases'].append(record)
            if runtime.failed:
                break
        return 0 if len(report['cases']) == len(jobs) and all(c.get('matches_real_generation') for c in report['cases']) else 1
    finally:
        if server:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        process = runtime.process
        runtime.stop()
        report['runtime_stopped'] = process is None or process.poll() is not None
        report['runtime_error'] = runtime.error
        report['memory_samples'] = list(runtime.memory_samples)
        target = 'post-patch-validation.json' if args.post_patch else 'generation-diagnostic.json'
        (folder / target).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'blocked_reason': report.get('blocked_reason'),
                          'runtime_stopped': report['runtime_stopped'], 'cases': [
            {'name': c['name'], 'delivered': c.get('delivered'), 'seconds': c['seconds'],
             'stop_type': c.get('raw', [{}])[0].get('response', {}).get('stop_type') if c.get('raw') else None,
             'error': c.get('error')} for c in report['cases']]}, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    raise SystemExit(main())
