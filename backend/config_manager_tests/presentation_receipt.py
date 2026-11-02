"""Read-only sanitized acceptance receipt, scoped to this disposable installation."""
import json
import os
from pathlib import Path
from psycopg.rows import dict_row
from presentation_fixture import connect, INSTALLATION, CAPABILITIES

with connect() as conn:
    conn.execute('SET TRANSACTION READ ONLY')
    with conn.cursor(row_factory=dict_row) as cur:
        result = {'installation_id': INSTALLATION, 'test_capabilities_only': CAPABILITIES.revision}
        for name, query in {
            'installation': 'SELECT * FROM hs_config.installation WHERE installation_id=%s',
            'revisions': 'SELECT revision,document,fingerprint,created_at FROM hs_config.revision WHERE installation_id=%s ORDER BY revision',
            'operations': 'SELECT operation_id,revision,status,fence,required_components FROM hs_config.operation WHERE installation_id=%s ORDER BY revision',
            'audit': 'SELECT * FROM hs_config.audit WHERE installation_id=%s ORDER BY id',
            'receipts': 'SELECT r.* FROM hs_config.receipt r JOIN hs_config.operation o USING(operation_id) WHERE o.installation_id=%s ORDER BY recorded_at',
        }.items():
            cur.execute(query, (INSTALLATION,))
            result[name] = cur.fetchall()
        cur.execute('SELECT clock_timestamp() AS utc,current_setting(\'TimeZone\') AS database_timezone')
        result.update(cur.fetchone())
        cur.execute("SELECT event,result,at FROM hs_admin_audit WHERE event='CONFIG_APPLY_REAUTH' ORDER BY id")
        result['reauth_audit'] = cur.fetchall()
    directory = Path(os.environ['HARPISENSE_PRESENTATION_TEST_DIRECTORY'])
    for filename in ('presentation.json', 'presentation-journal.json'):
        if (directory / filename).exists():
            result[filename] = json.loads((directory / filename).read_text())
    print(json.dumps(result, default=str, ensure_ascii=False, indent=2))
