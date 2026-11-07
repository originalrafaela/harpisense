"""Read the actual Ubuntu artifact and require product contracts and provenance."""
import hashlib
import io
import json
import re
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]
artifact = ROOT/'dist/HarpiSense-Setup-Ubuntu-24.04-x86_64.run'
blob = artifact.read_bytes()
assert hashlib.sha256(blob).hexdigest() == artifact.with_suffix('.run.sha256').read_text().split()[0]
with tarfile.open(fileobj=io.BytesIO(blob.split(b'\n__HARPI_PAYLOAD__\n',1)[1]),mode='r:gz') as archive:
    build = json.load(archive.extractfile('payload/backend/native_server/build_info.json'))
    assert re.fullmatch('[0-9a-f]{40}', build['source_commit'])
    subprocess.check_call(['git','cat-file','-e',build['source_commit']+'^{commit}'],cwd=ROOT)
    assert build['package_version'] == 'native-installers-20261106-candidate.5'
    for path in ('backend/admin_auth/003_password_reset.sql','backend/config_manager/003_assets.sql',
                 'backend/delivery/002_operational_authority.sql','backend/config_manager/assets.py',
                 'backend/delivery/operational_queue.py','backend/domain/harpisense_engines/routing.py'):
        expected = subprocess.check_output(['git','show',build['source_commit']+':'+path],cwd=ROOT)
        assert archive.extractfile('payload/'+path).read().replace(b'\r\n',b'\n') == expected.replace(b'\r\n',b'\n'), path
    assert archive.extractfile('payload/frontend/dist/index.html').read() == (ROOT/'frontend/dist/index.html').read_bytes()
print(json.dumps({'artifact_sha256':hashlib.sha256(blob).hexdigest(),'build':build,
                  'product_contracts_and_provenance':'passed'}))
