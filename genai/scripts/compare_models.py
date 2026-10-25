"""Six fixed synthetic cases/model, sequential native processes, no operational use."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import threading
import time
import urllib.request

from genai.harpia.client import Client, post_json
from genai.harpia.contracts import SYSTEM, valid_text
from genai.harpia.memory import MemoryPolicy, available_memory, process_memory
from genai.harpia.qwen import QwenRuntime
from genai.harpia.runtime import Runtime
from genai.harpia.server import LocalServer


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class Audit:
    def _observe_completion(self, payload, response):
        self.raw.append({'request': payload, 'response': response})


class BitNetComparison(Audit, Runtime):
    model_id = 'BitNet-b1.58-2B-4T-I2_S'
    text_source = 'bitnet_unverified_text'


class QwenComparison(Audit, QwenRuntime):
    pass


def props(runtime):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(runtime.url + '/props', timeout=3) as response:
        return json.loads(response.read(65536))


def run_model(kind, bitnet_root, cases, results):
    local = Path('.local-harpia/comparison')
    record = {'model': kind, 'memory_before': available_memory(), 'cases': []}
    runtime = (BitNetComparison if kind == 'bitnet' else QwenComparison)(
        'http://127.0.0.1:8094', 45, MemoryPolicy(), 96)
    runtime.raw = []
    server = thread = None
    try:
        reason = runtime.memory_policy.entry_reason(record['memory_before'])
        if reason:
            record['blocked_reason'] = reason
            return record
        if kind == 'bitnet':
            config = json.loads((bitnet_root / 'genai/config.example.json').read_text(encoding='utf-8'))
            executable, model = bitnet_root / config['runtime_executable'], bitnet_root / config['model_path']
            manifest = json.loads((bitnet_root / '.local-harpia/results/build-manifest.json').read_text(encoding='utf-8'))
            patch_lock = json.loads(Path('genai/artifacts.lock.json').read_text(encoding='utf-8'))['runtime']['local_patch']
            if manifest['source_sha256'] != patch_lock['patched_source_sha256'] or manifest['patch'] != patch_lock['id']:
                raise ValueError('BitNet build is not the pinned scoped activation patch')
            expected = manifest['binaries']['llama-server']['sha256']
            record['build_manifest'] = manifest
            model_lock = json.loads(Path('genai/artifacts.lock.json').read_text(encoding='utf-8'))['model']
        else:
            install = json.loads((local / 'installed.json').read_text(encoding='utf-8-sig'))
            lock = json.loads(Path('genai/comparison-artifacts.lock.json').read_text(encoding='utf-8-sig'))
            executable, model = Path(install['executable']), local / lock['model']['filename']
            # Validate every extracted executable/DLL against the install manifest.
            for artifact in install['files']:
                if sha(local / artifact['path']) != artifact['sha256']:
                    raise ValueError('dedicated runtime artifact differs from manifest')
            expected = next(a['sha256'] for a in install['files'] if Path(a['path']).name == 'llama-server.exe')
            model_lock = lock['model']
            record['installed_runtime'] = install
            if executable.resolve() == (bitnet_root / '.local-harpia/runtime/BitNet/build/bin/Release/llama-server.exe').resolve():
                raise ValueError('Qwen must not reuse patched BitNet runtime')
        record.update(executable=str(executable.resolve()), executable_sha256=sha(executable),
                      model_sha256=sha(model), model_bytes=model.stat().st_size)
        if record['executable_sha256'] != expected or record['model_sha256'] != model_lock['sha256']:
            raise ValueError('model/runtime integrity mismatch')
        if not runtime.start(executable, model, local / 'logs' / kind, threads=2, context=1024):
            record['blocked_reason'] = runtime.error
            return record
        record['load_seconds'] = runtime.load_seconds
        record['runtime_properties'] = props(runtime)
        if kind == 'qwen':
            # Formatting only, no generation: prove local framing matches embedded official non-thinking template.
            probe = post_json(runtime.url + '/apply-template', {
                'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': 'Dados sintéticos.'}],
                'add_generation_prompt': True, 'chat_template_kwargs': {'enable_thinking': False}}, 5)
            record['template_probe'] = probe
            if probe.get('prompt') != runtime.frame_data('Dados sintéticos.'):
                raise ValueError('embedded template differs from explicit non-thinking framing')
        # Service authentication reused; random token is never persisted in evidence.
        token = os.urandom(24).hex()
        server = LocalServer(('127.0.0.1', 0), runtime, token)
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.02})
        thread.start()
        client = Client(f'http://127.0.0.1:{server.server_port}', token, timeout=60,
                        expected_model=runtime.model_id, expected_source=runtime.text_source)
        for case in cases:
            before = len(runtime.raw)
            start = time.monotonic()
            item = {'name': case['name'], 'input': case, 'memory_before': available_memory()}
            try:
                if 'instruction' in case:
                    text = runtime.complete(runtime.frame_data(case['instruction']), 96)
                    output = {'text': text, 'source': runtime.text_source, 'model_id': runtime.model_id,
                              'path': 'direct_runtime_no_adapter'}
                else:
                    output = client.explanation(case['context'])
                raw = runtime.raw[before:]
                item.update(output=output, raw=raw, budget=runtime.last_budget,
                            model_origin_proven=(len(raw) == 1 and output.get('source') == runtime.text_source
                                and output.get('text') == valid_text(raw[0]['response'].get('content'))))
            except Exception as exc:
                item.update(error=type(exc).__name__, runtime_error=runtime.error, raw=runtime.raw[before:])
            item.update(seconds=time.monotonic()-start, memory_after=available_memory(),
                        process_memory=process_memory(runtime.process) if runtime.process else None)
            record['cases'].append(item)
            print(json.dumps({'model': kind, 'case': case['name'], 'output': item.get('output'),
                              'error': item.get('error')}, ensure_ascii=True), flush=True)
            if runtime.failed:
                break
        return record
    except Exception as exc:
        record['error'] = type(exc).__name__ + ': ' + str(exc)
        return record
    finally:
        if server:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        process = runtime.process
        runtime.stop()
        record['stopped'] = process is None or process.poll() is not None
        record['memory_samples'] = list(runtime.memory_samples)
        record['runtime_error'] = runtime.error
        # Persist even if the next model is memory-blocked or interrupted.
        (results / (kind + '-comparison.json')).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bitnet-root', type=Path, default=Path('../harpia-bitnet'))
    parser.add_argument('--model', choices=['all', 'bitnet', 'qwen'], default='all')
    args = parser.parse_args()
    cases = json.loads(Path('genai/comparison_cases.json').read_text(encoding='utf-8'))
    results = Path('.local-harpia/comparison/results')
    results.mkdir(parents=True, exist_ok=True)
    records = []
    for kind in (['bitnet', 'qwen'] if args.model == 'all' else [args.model]):
        records.append(run_model(kind, args.bitnet_root.resolve(), cases, results))
    return 0 if all(len(r['cases']) == len(cases) and all(c.get('model_origin_proven') for c in r['cases']) for r in records) else 1


if __name__ == '__main__':
    raise SystemExit(main())
