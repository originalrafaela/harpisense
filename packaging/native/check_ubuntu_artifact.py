"""Run inside disposable Linux/Python 3.12; only the .run artifact is mounted."""
from pathlib import Path
import io
import os
import subprocess
import sys
import tarfile

artifact = Path(sys.argv[1]).read_bytes()
payload = artifact.split(b'\n__HARPI_PAYLOAD__\n', 1)[1]
with tarfile.open(fileobj=io.BytesIO(payload), mode='r:gz') as archive:
    archive.extractall('/tmp/artifact-test', filter='data')
root = Path('/tmp/artifact-test/payload')
subprocess.run([sys.executable, '-m', 'venv', '/tmp/runtime-test'], check=True)
python = '/tmp/runtime-test/bin/python'
subprocess.run([python, '-m', 'pip', 'install', '--no-index', '--find-links',
                str(root/'wheels'), '-r', str(root/'requirements.lock')], check=True)
env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME')}
command = [python, '-I', str(root/'packaging/native/entry.py'), 'check-runtime']
subprocess.run(command, cwd='/', env=env, check=True)
# Reproduce the original packaging omission and require fail-closed behavior.
catalog = root/'backend/domain/harpisense_catalog.py'
catalog.rename(catalog.with_suffix('.disabled'))
failure = subprocess.run(command, cwd='/', env=env, capture_output=True, text=True)
assert failure.returncode != 0 and "No module named 'harpisense_catalog'" in failure.stderr
print('MISSING_CATALOG_REJECTED_BEFORE_DATABASE')
