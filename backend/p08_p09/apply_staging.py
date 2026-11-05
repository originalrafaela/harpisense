"""Exact-hash staging update; default dry-run. No services, collectors or SQL.

Run as root for the real root-owned target. Only two approved files are replaced.
"""
import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

EXPECTED = {
    'auxiliary_audit_adapter.py': ('a6e2747e9cf857216297db1a9557fa12925e4e1c088b27152a0fcfbea8c827ff', '04b58d66d5d6d9cd513bff4b559c187bca4a2d13ea370e80fcbfc97bb9eb5416'),
    'p08_p09_pipeline.py': ('a43d0db34a5c6bca409248d8b464bdacafa3ed93e7eddd34da0fa2de1f4b85cf', '4ec9ed8c2fb5b068ebdae4b6cd7643d1aca5a5c0fcc5d9c354e28f5f7f12d8dc'),
}
DEPENDENCIES = {
    'p08_artifact_validator.py': '58868a25ff791139025e10321497bda27fb77e26e5d6f6fc31936eba530c65b7',
    'log_coverage_integration.py': 'e0b47ed6124d49a68a6e31d7e829c91847164e8ba85c3bc3ab9768c1ebe24bfa',
    'coverage_gate.py': '3310a15e11b90ece09c4e8f4ba49b7c0eab7686bafefec19b85447b1693c6109',
}
DEFAULT_TARGET = Path('/opt/harpisense/staging/p09-deteccao-decisao/adaptador_logs_p08_p09')

def digest(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'Not a regular file: {path.name}')
    return hashlib.sha256(path.read_bytes()).hexdigest()

def apply(target, candidates, *, write=False):
    target, candidates = Path(target), Path(candidates)
    if target.is_symlink() or candidates.is_symlink():
        raise ValueError('Symlink directory rejected')
    def check_current():
        for name, expected in {**DEPENDENCIES, **{k: v[0] for k, v in EXPECTED.items()}}.items():
            if digest(target / name) != expected:
                raise ValueError(f'Unexpected current hash: {name}')
    check_current()
    for name, (_, new) in EXPECTED.items():
        if digest(candidates / name) != new:
            raise ValueError(f'Unexpected candidate hash: {name}')
        compile((candidates / name).read_bytes(), name, 'exec')
    receipt = dict(target=str(target), applied=False,
                   files={name: dict(before=old, after=new) for name, (old, new) in EXPECTED.items()})
    if not write: return receipt
    backup = Path(tempfile.mkdtemp(prefix='.validated-batch-backup-', dir=target))
    receipt['backup_directory'] = str(backup)
    for name in EXPECTED:
        shutil.copy2(target / name, backup / name)
    def replace(name, source):
        current = (target / name).stat()
        fd, tmp = tempfile.mkstemp(prefix='.' + name + '.', dir=target)
        tmp = Path(tmp)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(source.read_bytes())
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(tmp, current.st_mode)
            os.chown(tmp, current.st_uid, current.st_gid)
            os.replace(tmp, target / name)
        finally:
            if tmp.exists(): tmp.unlink()
    check_current()
    try:
        for name in EXPECTED:
            replace(name, candidates / name)
        for name, (_, expected) in EXPECTED.items():
            if digest(target / name) != expected:
                raise ValueError('Post-update hash mismatch')
    except BaseException:
        for name in EXPECTED:
            replace(name, backup / name)
        raise
    receipt['applied'] = True
    (backup / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--target-dir', type=Path, default=DEFAULT_TARGET)
    parser.add_argument('--candidate-dir', type=Path, default=Path(__file__).parent / 'adaptador_logs_p08_p09')
    args = parser.parse_args()
    print(json.dumps(apply(args.target_dir, args.candidate_dir, write=args.apply), indent=2))
