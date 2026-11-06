"""Operate only the identified disposable Ubuntu VM; retain sanitized evidence."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
ACCESS = ROOT / '.native-test/candidate2-clean-20261106'
EVIDENCE = ROOT / 'docs/evidence/native-installers/ubuntu-candidate3-trial'
HOST = '192.168.155.148'
OPTIONS = ['-i', str(ACCESS / 'trial_ed25519'), '-o',
           'UserKnownHostsFile="' + (ACCESS / 'known_hosts').as_posix() + '"',
           '-o', 'StrictHostKeyChecking=yes', '-o', 'BatchMode=yes',
           '-o', 'ConnectTimeout=10']
SSH = ['ssh', *OPTIONS, 'trial@' + HOST]


def remote(command):
    return subprocess.run(SSH + [command], capture_output=True, text=True, encoding='utf-8')


def main():
    phase = sys.argv[1]
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    identity = remote('hostname; sudo cat /sys/class/dmi/id/product_uuid; '
                      'cat /etc/machine-id; cat /proc/sys/kernel/random/boot_id; ip -brief address')
    if (identity.returncode or 'harpisense-candidate2-clean' not in identity.stdout or
            'd4a14d56-fdae-2078-5ea1-71445a76a25f' not in identity.stdout.lower()):
        print(identity.stdout + identity.stderr)
        raise SystemExit('DISPOSABLE_GUEST_IDENTITY_NOT_CONFIRMED')
    (EVIDENCE / (phase + '-identity.txt')).write_text(
        '\n'.join(line.rstrip() for line in identity.stdout.splitlines()) + '\n', encoding='utf-8')
    if phase == 'probe':
        result = remote('set -eu; test ! -e /opt/harpisense; test ! -e /var/lib/harpisense; '
                        'test ! -e /usr/lib/postgresql/16; test ! -e /usr/sbin/mosquitto; '
                        'echo CLEAN_GUEST_CONFIRMED; cat /etc/os-release; uname -m')
    elif phase == 'install':
        base = ('https://github.com/originalrafaela/harpisense/releases/download/'
                'native-installers-20261106-candidate.3/')
        name = 'HarpiSense-Setup-Ubuntu-24.04-x86_64.run'
        result = remote('set -eu; mkdir -p /home/trial/harpisense-trial; '
            'cd /home/trial/harpisense-trial; curl -fL --retry 3 -o ' + name + ' ' + base + name + '; '
            'curl -fL --retry 3 -o ' + name + '.sha256 ' + base + name + '.sha256; '
            'echo "72b0e0776d44ea2f6ad1b4dffbc3815932270177ba1c1f6de82e5ffd23468b65  ' + name + '" | sha256sum -c -; '
            'sha256sum -c ' + name + '.sha256; sudo sh ' + name)
    elif phase in ('before-reboot', 'after-reboot'):
        subprocess.run(['scp', *OPTIONS, str(ROOT / 'packaging/native/acceptance_ubuntu_guest.py'),
                        'trial@' + HOST + ':/home/trial/harpisense-trial/acceptance_ubuntu_guest.py'], check=True)
        result = remote('sudo /opt/harpisense/venv/bin/python '
                        '/home/trial/harpisense-trial/acceptance_ubuntu_guest.py ' + phase)
    elif phase in ('reboot', 'shutdown'):
        result = remote('sudo ' + ('reboot' if phase == 'reboot' else 'shutdown -h now'))
    elif phase == 'provenance':
        result = remote('sudo sha256sum /opt/harpisense/backend/admin_auth/service.py; '
                        '/usr/lib/postgresql/16/bin/postgres --version')
        expected = hashlib.sha256((ROOT / 'backend/admin_auth/service.py').read_bytes()).hexdigest()
        if result.returncode or result.stdout.split()[0] != expected:
            raise SystemExit('INSTALLED_BACKEND_SOURCE_HASH_MISMATCH')
    else:
        raise SystemExit('UNKNOWN_PHASE')
    output = result.stdout + result.stderr
    (EVIDENCE / (phase + '.txt')).write_text(output, encoding='utf-8')
    if phase in ('before-reboot', 'after-reboot'):
        report = json.loads(result.stdout)
        (EVIDENCE / (phase + '.json')).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(output, end='')
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
