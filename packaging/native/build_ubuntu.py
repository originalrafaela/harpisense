"""Create a self-extracting Ubuntu 24.04 installer on any build platform."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[2]


def main():
    stage = ROOT/('.native-build/ubuntu-' + str(time.time_ns()))
    stage.mkdir(parents=True)
    for source, target in [('frontend/dist', 'frontend/dist')]:
        shutil.copytree(ROOT/source, stage/target, ignore=shutil.ignore_patterns('__pycache__'))
    scripts = stage/'packaging/native'
    scripts.mkdir(parents=True)
    for name in ('entry.py', 'provision.py', 'ubuntu_install.py'):
        shutil.copyfile(ROOT/'packaging/native'/name, scripts/name)
    for name in ('delivery', 'admin_auth', 'config_manager', 'native_server'):
        shutil.copytree(ROOT/'backend'/name, stage/'backend'/name,
                        ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(ROOT/'backend/domain/harpisense_contracts', stage/'backend/domain/harpisense_contracts',
                    ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(ROOT/'genai/harpia', stage/'genai/harpia', ignore=shutil.ignore_patterns('__pycache__'))
    requirements = []
    for name in ('backend/delivery/requirements.txt', 'backend/config_manager/requirements.txt',
                 'backend/admin_auth/requirements-mfa.txt'):
        requirements.extend((ROOT/name).read_text().splitlines())
    requirements.append('paho-mqtt==2.1.0')
    (stage/'requirements.lock').write_text('\n'.join(requirements) + '\n')
    subprocess.run([sys.executable, '-m', 'pip', 'download', '--dest', str(stage/'wheels'),
        '--platform', 'manylinux_2_34_x86_64', '--platform', 'manylinux_2_28_x86_64',
        '--platform', 'manylinux2014_x86_64', '--python-version', '312', '--implementation', 'cp',
        '--abi', 'cp312', '--only-binary=:all:', '-r', str(stage/'requirements.lock')], check=True)
    # Freeze every wheel version, rather than resolving transitive versions on target.
    wheels = sorted((stage/'wheels').glob('*.whl'))
    (stage/'requirements.lock').write_text('\n'.join(
        name.name.split('-')[0].replace('_', '-') + '==' + name.name.split('-')[1] for name in wheels) + '\n')
    (stage/'WHEELS.sha256').write_text('\n'.join(hashlib.sha256(w.read_bytes()).hexdigest() + '  wheels/' + w.name for w in wheels) + '\n')
    archive = ROOT/'.native-build/ubuntu-payload.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        tar.add(stage, arcname='payload')
    header = '''#!/bin/sh
set -eu
if [ "$(id -u)" != 0 ]; then
  if command -v pkexec >/dev/null 2>&1; then exec pkexec "$0" "$@"; fi
  echo 'Execute este instalador como administrador (sudo).'; exit 1
fi
work=$(mktemp -d /tmp/harpisense-setup.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT HUP INT TERM
line=$(awk '/^__HARPI_PAYLOAD__$/ {print NR + 1; exit}' "$0")
tail -n +"$line" "$0" | tar -xz -C "$work"
python3 "$work/payload/packaging/native/ubuntu_install.py" --payload "$work/payload" "$@"
exit 0
__HARPI_PAYLOAD__
'''
    artifact = ROOT/'dist/HarpiSense-Setup-Ubuntu-24.04-x86_64.run'
    artifact.parent.mkdir(exist_ok=True)
    with artifact.open('wb') as output:
        output.write(header.encode())
        with archive.open('rb') as source:
            shutil.copyfileobj(source, output)
    artifact.chmod(0o755)
    artifact.with_suffix('.run.sha256').write_text(hashlib.sha256(artifact.read_bytes()).hexdigest() + '  ' + artifact.name + '\n')


if __name__ == '__main__':
    main()
