"""Sanitized read-only receipt for the disposable browser fixture."""
import json
from psycopg.rows import dict_row
from browser_fixture import connect, CAPABILITIES

with connect() as conn:
    conn.execute('SET TRANSACTION READ ONLY')
    with conn.cursor(row_factory=dict_row) as cur:
        receipt = {'capabilities_revision': CAPABILITIES.revision,
                   'capabilities_are_test_only': True}
        for name, query in {
            'installation': 'SELECT * FROM hs_config.installation',
            'operations': 'SELECT operation_id,installation_id,revision,status FROM hs_config.operation ORDER BY revision',
            'progress': 'SELECT * FROM hs_config.setup_progress',
            'configuration_audit': 'SELECT * FROM hs_config.audit ORDER BY id',
            'setup_audit': 'SELECT * FROM hs_config.setup_audit ORDER BY id',
            'admin_audit': 'SELECT id,event,at,result FROM hs_admin_audit ORDER BY id',
            'sessions': 'SELECT count(*) AS total,count(revoked_at) AS revoked FROM hs_admin_session',
            'projections': 'SELECT count(*) AS count FROM projections',
        }.items():
            cur.execute(query)
            receipt[name] = cur.fetchall()
        cur.execute('SELECT clock_timestamp() AS utc')
        receipt.update(cur.fetchone())
        print(json.dumps(receipt, default=str, ensure_ascii=False, indent=2))
