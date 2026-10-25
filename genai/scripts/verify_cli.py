"""Primeira geração curta diretamente no llama-cli oficial; sem HarpIA/fallback."""
import json
import hashlib
import os
from pathlib import Path
import subprocess
import time

from genai.harpia.contracts import CHAT_TEMPLATE, SYSTEM
from genai.harpia.runtime import available_memory
from .verify_local import cpu_seconds, working_set


def generated_text_from_cli(stdout, prompt):
    """Ignore banner/prompt/timings; absence of native framing is not success."""
    stdout = stdout.replace('\r\n', '\n')
    echo = '\n> ' + prompt + '\n'
    if echo not in stdout:
        return ''
    suffix = stdout.split(echo, 1)[1]
    if '[ Prompt:' not in suffix:
        return ''
    return suffix.split('[ Prompt:', 1)[0].strip()


def main():
    config = json.loads(Path('genai/config.example.json').read_text())
    folder = Path('.local-harpia/results')
    folder.mkdir(parents=True, exist_ok=True)
    executable = Path(config['runtime_executable']).with_name('llama-cli.exe').resolve()
    model = Path(config['model_path']).resolve()
    data = {'synthetic': True, 'device': 'poste-2', 'status': 'offline',
            'observed_at': '2026-10-24T14:00:00Z', 'cause': 'unknown'}
    text = ('Dados sintéticos de teste: ' + json.dumps(data)
            + '. Em uma frase curta em português, descreva o estado e diga que a causa é desconhecida.')
    report = {'kind': 'real_native_cli', 'synthetic_input': data,
              'chat_template': CHAT_TEMPLATE,
              'memory_before': available_memory(), 'inference_executed': False,
              'generation': {'max_tokens': 48, 'temperature': 0, 'seed': 42,
                             'threads': 2, 'context_tokens': 1024, 'gpu_layers': 0}}
    process = None
    try:
        if not executable.is_file() or not model.is_file():
            report['blocked_reason'] = 'native_cli_or_model_missing'
            return 2
        if report['memory_before'] and report['memory_before']['available_bytes'] < (config['reserve_memory_mb'] + 2560) * 1024**2:
            report['blocked_reason'] = 'insufficient_available_memory'
            return 2
        with model.open('rb') as weights:
            report['model_sha256'] = hashlib.file_digest(weights, 'sha256').hexdigest()
        expected = json.loads(Path('genai/artifacts.lock.json').read_text())['model']['sha256']
        if report['model_sha256'] != expected:
            report['blocked_reason'] = 'model_integrity_mismatch'
            return 2
        command = [str(executable), '-m', str(model), '--jinja', '--chat-template', CHAT_TEMPLATE,
                   '-sys', SYSTEM, '-p', text, '-n', '48', '-t', '2',
                   '-c', '1024', '-ngl', '0', '--temp', '0', '--seed', '42',
                   '--single-turn', '--simple-io', '--color', 'off', '--show-timings']
        with open(folder / 'cli-stdout.txt', 'wb') as output, open(folder / 'cli-stderr.txt', 'wb') as errors:
            start = time.monotonic()
            environment = {k: v for k, v in os.environ.items() if not k.startswith('LLAMA_')}
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=output, stderr=errors,
                                       env=environment, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            report['pid'] = process.pid
            peak = 0
            while process.poll() is None:
                memory = working_set(process)
                if memory:
                    peak = max(peak, memory['peak_working_set_bytes'])
                if time.monotonic() - start > 120:
                    report['failed_reason'] = 'cli_timeout_120_seconds'
                    return 1
                time.sleep(0.1)
            report.update(exit_code=process.returncode, load_and_generation_seconds=time.monotonic() - start,
                          sampled_peak_working_set_bytes=peak, cpu_seconds=cpu_seconds(process))
        answer = (folder / 'cli-stdout.txt').read_text(encoding='utf-8', errors='replace').strip()
        report['native_stdout'] = answer
        # The pinned CLI prints a banner and echoes the prompt. Only the text
        # between that exact echo and its native timings is model output.
        generated = generated_text_from_cli(answer, text)
        report['generated_text'] = generated
        report['inference_executed'] = process.returncode == 0 and bool(generated)
        # Timing breakdown is retained in native stderr; total is not called load time.
        return 0 if report['inference_executed'] else 1
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        report['process_stopped'] = process is None or process.poll() is not None
        output = json.dumps(report, ensure_ascii=False, indent=2)
        (folder / 'real-cli.json').write_text(output, encoding='utf-8')
        print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    raise SystemExit(main())
