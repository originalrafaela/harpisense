"""Build a source-identified, secret-free gateway upgrade archive."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    files = {}
    for directory in ('backend', 'genai/harpia', 'frontend/dist'):
        for path in (ROOT/directory).rglob('*'):
            if path.is_file() and not any(p.startswith('.') or p in ('__pycache__', 'node_modules') for p in path.relative_to(ROOT).parts):
                if directory == 'frontend/dist' or path.suffix in ('.py','.sql','.json','.txt','.toml'):
                    files[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    for source, target in [('gateway_entry.py','gateway_entry.py'),('upgrade_gateway.py','upgrade_gateway.py'),('requirements.txt','requirements.txt')]:
        files[target] = (Path(__file__).parent/source).read_bytes()
    base = '/opt/harpisense/staging/p11-postgresql'
    settings = {'base': base, 'installation_id': 'harpiserver-presentation',
        'expected_app_sha256': 'd8dc01de8ee14ca4daa31d34408882ef2a22a1d7858cad46abdd308bb0e957a9',
        'capability_revision': 'harpiserver-presentation-only-20261102',
        'key_file': base + '/.initial-auth-private/admin-mfa.key',
        'presentation_directory': base + '/presentation-state',
        'allowed_origins': ['http://127.0.0.1:4174','http://127.0.0.1:5174','http://127.0.0.1:8000'],
        'bitnet_enabled': False, 'bitnet_url': 'http://127.0.0.1:8091'}
    files['settings.json'] = json.dumps(settings, indent=2).encode()
    source = subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip()
    files['manifest.json'] = json.dumps({'source_commit': source,
        'working_tree_diff_sha256': hashlib.sha256(subprocess.check_output(['git','diff','HEAD'], cwd=ROOT)).hexdigest(),
        'files': {name: hashlib.sha256(value).hexdigest() for name,value in files.items()}}, indent=2).encode()
    import io
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, 'w:gz') as archive:
        for name, data in sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), 0o600
            archive.addfile(info, io.BytesIO(data))
    print(json.dumps({'archive': str(output), 'sha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'files':len(files)}))


if __name__ == '__main__':
    main()
