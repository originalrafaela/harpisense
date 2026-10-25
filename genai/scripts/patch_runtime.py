"""Minimal, pinned and idempotent local FFN correction; no weights modified."""
import hashlib
import json
from pathlib import Path
import subprocess
import argparse

SOURCE_SHA = 'd7bf43b007b97c38e7110932846c02361eb15b351850b8c1a5bcdc36e25daea5'
PREVIOUS_SHA = '5dfd6758d25c0e632100a305b31297882a817b9c8c33a3226f08141d2fa1a4ec'
PATCHED_SHA = 'e0d5113c65d15adc0ed713a43095001c747b9e036db0bd688588415bab0256b8'
OLD = b'LLM_FFN_SILU, LLM_FFN_PAR, il);'
PREVIOUS = b'n_layer == 30 ? LLM_FFN_RELU_SQR : LLM_FFN_SILU, LLM_FFN_PAR, il);'
# Pinned 2B-4T signature, not a rule that every 30-layer architecture uses ReLU2.
NEW = (b'(arch == LLM_ARCH_BITNET_B158 && n_layer == 30 && n_embd == 2560 '
       b'&& hparams.n_ff() == 6912 && hparams.n_head() == 20 '
       b'&& hparams.n_head_kv() == 5 && model.vocab.n_tokens() == 128256) '
       b'? LLM_FFN_RELU_SQR : LLM_FFN_SILU, LLM_FFN_PAR, il);')


def patched_source(data):
    digest = hashlib.sha256(data).hexdigest()
    if digest == PATCHED_SHA:
        return data
    needle = PREVIOUS if digest == PREVIOUS_SHA else OLD
    if digest not in (SOURCE_SHA, PREVIOUS_SHA) or data.count(needle) != 1:
        raise ValueError('unexpected runtime source; refusing to overwrite')
    result = data.replace(needle, NEW)
    if hashlib.sha256(result).hexdigest() != PATCHED_SHA:
        raise ValueError('runtime patch integrity mismatch')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--record-build', action='store_true')
    args = parser.parse_args()
    root = Path('.local-harpia/runtime/BitNet')
    lock = json.loads(Path('genai/artifacts.lock.json').read_text())['runtime']
    for folder, expected in ((root, lock['revision']), (root / '3rdparty/llama.cpp', lock['llama_cpp_submodule'])):
        actual = subprocess.check_output(['git', '-C', str(folder), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != expected:
            raise ValueError('unexpected runtime revision')
    source = root / '3rdparty/llama.cpp/src/models/bitnet.cpp'
    if args.record_build:
        if hashlib.sha256(source.read_bytes()).hexdigest() != PATCHED_SHA:
            raise ValueError('build source does not match scoped activation patch')
        report = {'patch': lock['local_patch']['id'], 'source_sha256': PATCHED_SHA,
                  'runtime_revision': lock['revision'], 'submodule_revision': lock['llama_cpp_submodule'],
                  'binaries': {}}
        for name in ('llama-cli', 'llama-server'):
            binary = root / 'build/bin/Release' / (name + '.exe')
            if binary.stat().st_mtime < source.stat().st_mtime:
                raise ValueError('binary older than patched source; rebuild required')
            report['binaries'][name] = {'path': str(binary.resolve()),
                'sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                'version': subprocess.check_output([str(binary.resolve()), '--version'], stderr=subprocess.STDOUT, text=True).strip()}
        Path('.local-harpia/results/build-manifest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report))
        return
    data = source.read_bytes()
    result = patched_source(data)
    if result != data:
        source.write_bytes(result)
    report = {'patch': 'bitnet-2b4t-signature-relu2-v2', 'source_sha256': SOURCE_SHA,
              'patched_sha256': PATCHED_SHA, 'changed': result != data,
              'inference_after_patch': False}
    folder = Path('.local-harpia/results')
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'runtime-activation-patch.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
