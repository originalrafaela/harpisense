"""Operator-driven live presentation check; password/token never leave memory."""
import getpass
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

RELEASE = Path('/opt/harpisense/staging/p11-postgresql/.presentation-releases/presentation-20261102-r1')


def main():
    os.umask(0o077)
    sys.path.insert(0, str(RELEASE))
    import deploy
    import snapshot
    import psycopg

    assert deploy.sha(deploy.BASE/'app.py') == deploy.sha(RELEASE/'app.candidate.py')
    token = None

    def request(path, body=None, method=None, expected=200):
        headers = {'Origin': 'http://127.0.0.1:4174'}
        if token:
            headers['Authorization'] = 'Bearer '+token
        if body is not None:
            headers['Content-Type'] = 'application/json'
        req = urllib.request.Request('http://127.0.0.1:8000/api/v1/'+path,
            data=None if body is None else json.dumps(body).encode(), headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as error:
            status, raw = error.code, error.read()
        assert status == expected, f'{path}: HTTP {status}; expected {expected}'
        return json.loads(raw) if raw else None

    def projections():
        with psycopg.connect(deploy.config()['HARPISENSE_DATABASE_URL']) as conn:
            conn.execute('SET TRANSACTION READ ONLY')
            return snapshot.receipt(conn)['public.projections']

    request('config/current', expected=401)
    username = input('Usuario administrativo existente: ')
    password = getpass.getpass('Senha atual (oculta): ')
    token = request('admin-auth/login', {'username': username, 'password': password})['access_token']
    try:
        request('admin-auth/session')
        request('p11/health')
        telemetry = request('p11/telemetry?limit=1')
        assert telemetry, 'Telemetry response empty'
        before = projections()
        current = request('config/current')
        # This command is for the initial deployment, not an overwrite of later work.
        assert current['desired_revision'] == 0 and current['effective_revision'] is None, 'Existing configuration: inspect before continuing'
        setup = request('config/setup')
        assert setup['version'] == 0, 'Existing wizard: inspect before continuing'
        name = input('Nome da instalacao [HarpiSense]: ').strip() or 'HarpiSense'
        zone = input('Fuso de exibicao [America/Sao_Paulo]: ').strip() or 'America/Sao_Paulo'
        from zoneinfo import ZoneInfo
        ZoneInfo(zone)
        parameters = {'display_name': name, 'timezone': zone}
        document = {'step': 'installation', 'parameters': parameters}
        saved = request('config/setup', {'expected_version': 0, 'idempotency_key': str(uuid4()), 'document': document}, 'PUT')
        resumed = request('config/setup')
        assert resumed['version'] == saved['version'] and resumed['document'] == document
        proposal = {'schema_version': '1.0.0', 'record_type': 'config.proposal',
            'request_id': str(uuid4()), 'idempotency_key': str(uuid4()), 'expected_revision': 0,
            'reason_code': 'ADMIN_CHANGE', 'document': {'schema_version': '1.0.0',
            'record_type': 'config.document', 'parameters': parameters}}
        operation = request('config/proposals', proposal)
        path = 'config/proposals/'+operation['operation_id']
        request(path+'/validate', {'expected_revision': 1})
        applied = request(path+'/apply', {'expected_revision': 1, 'current_password': password})
        assert applied['status'] == 'APPLIED', 'Application not confirmed; inspect recovery state'
        observed = request('config/presentation')
        assert observed['verified'] and observed['revision'] == 1 and observed['parameters'] == parameters
        assert observed['original_instant'] == '2026-11-01T12:00:00Z'
        retry = request(path+'/apply', {'expected_revision': 1, 'current_password': password})
        assert retry['status'] == 'APPLIED' and retry['idempotent']
        current = request('config/current')
        assert current['effective_revision'] == 1 and current['operational'] is False
        history = request('config/history')
        assert [row['event'] for row in history] == ['PROPOSED', 'VALIDATED', 'APPLYING', 'VERIFIED', 'APPLIED']
        assert projections() == before, 'Projection digest changed: investigate concurrent ingestion; do not restore'
        result = {'verified_at': datetime.now(timezone.utc).isoformat(), 'release': RELEASE.name,
            'live_http': True, 'login_session_health': True, 'wizard_saved_resumed': True,
            'proposal_validation_apply': True, 'idempotency': True, 'audit_sequence': True,
            'effective_revision': 1, 'presentation': observed, 'projections_unchanged': True,
            'telemetry': 'existing records queried; new MQTT ingestion not established', 'operational': False}
        destination = deploy.BASE/'.presentation-validation'
        destination.mkdir(mode=0o700, exist_ok=True)
        (destination/'verified.json').write_text(json.dumps(result, indent=2))
    finally:
        request('admin-auth/logout', {}, 'POST', expected=204)
        request('config/current', expected=401)
        password = token = None
    print('LIVE_PRESENTATION_VERIFIED; session revoked; operational=false; MQTT freshness not established')


if __name__ == '__main__':
    main()
