"""Run with the deployed venv on gateway; emits no environment values or secrets."""
import base64
import hashlib
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

base = Path('/opt/harpisense/staging/p11-postgresql')
package = Path('/opt/harpisense/integration-v2/HarpiSense_Pacote13_Integracao_Testes_v2')
env = dict(line.split('=', 1) for line in (base / '.env').read_text().splitlines()
           if '=' in line and not line.lstrip().startswith('#'))
files = [base / name for name in ['app.py', 'postgres_store.py', 'mqtt_consumer.py']]
files += [package / 'componentes/p11/backend11/service.py']
files += sorted((base / 'harpia_deterministic').glob('*.py'))
result = {'observed_at': datetime.now(timezone.utc).isoformat(),
          'base': str(base), 'environment_keys': sorted(env),
          'files': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
sys.path.insert(0, str(base))
from postgres_store import PostgresStore
store = PostgresStore(env['HARPISENSE_DATABASE_URL'])
with store._connect() as conn:
    conn.execute('SET TRANSACTION READ ONLY')
    result['database'] = conn.execute('SELECT current_database(), current_user').fetchone()
    result['counts'] = dict(conn.execute('SELECT kind, count(*) FROM projections GROUP BY kind').fetchall())
    result['latest_telemetry'] = [dict(id=r[0], revision=r[1], source=r[2], data=r[3], created_at=r[4].isoformat())
        for r in conn.execute("SELECT id, revision, source, data, created_at FROM projections WHERE kind='telemetry' ORDER BY created_at DESC LIMIT 3").fetchall()]
auth = base64.b64encode((env['HARPISENSE_ADMIN_USER'] + ':' + env['HARPISENSE_ADMIN_PASSWORD']).encode()).decode()
for path in ['health', 'telemetry?limit=3&offset=0']:
    request = urllib.request.Request('http://127.0.0.1:8000/api/v1/p11/' + path,
                                     headers={'Authorization': 'Basic ' + auth})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            result[path] = {'status': response.status, 'body': json.load(response)}
    except urllib.error.HTTPError as exc:
        result[path] = {'status': exc.code}
print(json.dumps(result, indent=2, ensure_ascii=False))
