"""Read-only gateway inventory. Never output environment values or account data."""
import importlib.util
import json
from pathlib import Path
import psycopg

base = Path('/opt/harpisense/staging/p11-postgresql')
env = dict(line.split('=', 1) for line in (base/'.env').read_text().splitlines()
           if '=' in line and not line.startswith('#'))
result = {'environment_names': sorted(env), 'dependencies': {
    name: importlib.util.find_spec(name) is not None
    for name in ('argon2', 'pyotp', 'qrcode', 'cryptography', 'psycopg', 'fastapi')},
    'base_writable': __import__('os').access(base, __import__('os').W_OK)}
with psycopg.connect(env['HARPISENSE_DATABASE_URL']) as conn:
    result['database'] = dict(zip(('role', 'database', 'superuser', 'create_role'), conn.execute(
        'SELECT current_user,current_database(),rolsuper,rolcreaterole FROM pg_roles WHERE rolname=current_user').fetchone()))
    result['tables'] = [dict(zip(('schema', 'name', 'owner'), row)) for row in conn.execute(
        "SELECT schemaname,tablename,tableowner FROM pg_tables WHERE schemaname IN ('public','hs_config') ORDER BY 1,2")]
    result['administrator_count'] = conn.execute('SELECT count(*) FROM hs_admin_account').fetchone()[0]
print(json.dumps(result))
