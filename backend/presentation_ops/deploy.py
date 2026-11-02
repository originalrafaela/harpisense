"""Guarded presentation release preparation. Never restart a service automatically."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

BASE = Path('/opt/harpisense/staging/p11-postgresql')
RELEASE = Path(__file__).resolve().parent
BACKUP = BASE/'.presentation-backups/20261102T200522453566Z'
INSTALLATION = 'harpiserver-presentation'
APP_HASH = '81950f60a288a95777da73c64ffdf28fa5dd9f871fcd5cd243ebff6cc76947e7'
CAPABILITY = 'harpiserver-presentation-only-20261102'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def config():
    return dict(line.split('=',1) for line in (BASE/'.env').read_text().splitlines()
                if '=' in line and not line.startswith('#'))


def checked():
    manifest = json.loads((RELEASE/'manifest.json').read_text())
    for name, expected in manifest['files'].items():
        path = (RELEASE/name).resolve()
        assert path.is_relative_to(RELEASE) and sha(path) == expected, 'Release mismatch'
    saved = json.loads((BACKUP/'backup.json').read_text())
    restored = json.loads((BACKUP/'restore-verified.json').read_text())
    assert restored['all_table_digests_match'] and restored['files_match']
    assert sha(BACKUP/'database.dump') == restored['dump_sha256'] == saved['dump_sha256']
    for name, entry in saved['files'].items():
        if '__pycache__' in Path(name).parts:
            continue
        assert sha(Path(name)) == entry['sha256'], 'Active file drift: '+name
    assert sha(BASE/'app.py') == APP_HASH
    return manifest


def migration_sql(runtime):
    first = (RELEASE/'config_manager/001_config_manager.sql').read_text()
    second = (RELEASE/'config_manager/002_setup.sql').read_text()
    # Apply once; refuse an unexpected existing schema instead of overwriting it.
    grants = sql.SQL('''
GRANT USAGE ON SCHEMA hs_config TO {role};
GRANT SELECT ON ALL TABLES IN SCHEMA hs_config TO {role};
GRANT INSERT,UPDATE ON hs_config.installation,hs_config.operation,hs_config.setup_progress TO {role};
GRANT INSERT ON hs_config.revision,hs_config.audit,hs_config.receipt,hs_config.setup_request,hs_config.setup_audit TO {role};
GRANT USAGE ON ALL SEQUENCES IN SCHEMA hs_config TO {role};
''').format(role=sql.Identifier(runtime)).as_string()
    return ('BEGIN; SELECT pg_advisory_xact_lock(7261103101);\n'+first+
            "\nINSERT INTO hs_config.migration VALUES(1,'"+hashlib.sha256(first.encode()).hexdigest()+"');\n"+
            second+"\nINSERT INTO hs_config.setup_schema VALUES(2,'"+hashlib.sha256(second.encode()).hexdigest()+"');\n"+
            grants+'COMMIT;\n')


def prepare():
    checked()
    original = (BASE/'app.py').read_text()
    old = "sys.path.insert(0, '/opt/harpisense/staging/p11-postgresql/.admin-auth-releases/admin-session-20261030-r1')"
    assert original.count(old) == 1 and original.count('    return app') == 1
    addition = '''    # Presentation-only extension; existing P11/Store/HarpIA composition preserved.
    from config_manager.schema import Capabilities
    from config_manager.store import ConfigStore
    from config_manager.api import install_config_api
    from config_manager.presentation import PresentationApplicator
    import psycopg
    config = ConfigStore(lambda: psycopg.connect(conninfo), Capabilities(revision=CAPABILITY_VALUE))
    presentation = PresentationApplicator(config, INSTALLATION_VALUE, DIRECTORY_VALUE)
    try:
        presentation.recover()
    except Exception:
        pass  # Unknown remains blocked by the approved applicator.
    install_config_api(app, config, installation_id=INSTALLATION_VALUE, presentation=presentation)
    app.state.presentation = presentation
    app.state.presentation_release = RELEASE_VALUE
'''.replace('CAPABILITY_VALUE', repr(CAPABILITY)).replace('INSTALLATION_VALUE', repr(INSTALLATION)).replace('DIRECTORY_VALUE', repr(str(BASE/'presentation-state'))).replace('RELEASE_VALUE', repr(RELEASE.name))
    candidate = original.replace(old, 'sys.path.insert(0, '+repr(str(RELEASE))+')\n    sys.path.append('+repr(str(RELEASE/'domain'))+')')
    candidate = candidate.replace('    return app',addition+'    return app')
    compile(candidate, 'app.candidate.py', 'exec')
    (RELEASE/'app.candidate.py').write_text(candidate)
    print(json.dumps(dict(candidate=str(RELEASE/'app.candidate.py'), sha256=sha(RELEASE/'app.candidate.py'),
                          backup=str(BACKUP), installation_id=INSTALLATION, operational=False)))


def migrate_live():
    assert os.geteuid() == 0, 'Run exact operator sudo command'
    checked()
    assert (RELEASE/'rehearsal.json').is_file(), 'Candidate rehearsal required'
    # Rehearse restoring source ownership/mode in the isolated file copy only.
    saved = json.loads((BACKUP/'backup.json').read_text())
    root = (BACKUP/'restore-files').resolve()
    for entry in saved['files'].values():
        target = (root/entry['copy']).resolve()
        assert target.is_relative_to(root) and not target.is_symlink()
        os.chown(target, entry['uid'], entry['gid'])
        os.chmod(target, entry['mode'])
        status = target.stat()
        assert (status.st_uid,status.st_gid,status.st_mode & 0o777) == (entry['uid'],entry['gid'],entry['mode'])
    (RELEASE/'restore-metadata.json').write_text(json.dumps(dict(owner_group_modes_match=True,isolated_only=True)))
    parameters = conninfo_to_dict(config()['HARPISENSE_DATABASE_URL'])
    dbname, runtime = parameters['dbname'], parameters['user']
    script = migration_sql(runtime)
    # Owner is postgres via peer; runtime never receives DDL privileges for hs_config.
    result = subprocess.run(['/usr/sbin/runuser','-u','postgres','--','/usr/bin/psql',
                             '-X','--set','ON_ERROR_STOP=1','--dbname',dbname],
                            input=script, text=True, capture_output=True)
    if result.returncode:
        (RELEASE/'migration.private.log').write_text(result.stderr)
        raise RuntimeError('Migration failed; inspect private log locally; no bootstrap activated')
    (RELEASE/'migration.json').write_text(json.dumps(dict(applied_at=datetime.now(timezone.utc).isoformat(),
        owner='postgres', runtime_ddl=False, schemas=['hs_config'], service_restarted=False)))
    print('CONFIG_SCHEMA_READY; no service restarted; bootstrap unchanged')


def activate():
    checked()
    assert (RELEASE/'migration.json').is_file() and (RELEASE/'rehearsal.json').is_file()
    candidate = RELEASE/'app.candidate.py'
    rehearsal = json.loads((RELEASE/'rehearsal.json').read_text())
    assert sha(candidate) == rehearsal['candidate_sha256']
    values = config()
    sys.path[:0] = [str(RELEASE), str(RELEASE/'domain')]
    from config_manager.store import ConfigStore
    from config_manager.schema import Capabilities
    from config_manager.setup import migrate_setup
    from config_manager.store import migrate
    connect = lambda: psycopg.connect(values['HARPISENSE_DATABASE_URL'])
    # These calls only compare installed checksums; no DDL if migration exists.
    migrate(connect)
    migrate_setup(connect)
    ConfigStore(connect, Capabilities(revision=CAPABILITY)).provision_registry(INSTALLATION)
    directory = BASE/'presentation-state'
    directory.mkdir(mode=0o700, exist_ok=False)
    temporary = BASE/'.app.presentation.new'
    with temporary.open('x') as stream:
        stream.write(candidate.read_text())
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temporary, (BASE/'app.py').stat().st_mode & 0o777)
    checked()  # Detect changes just before atomic replacement.
    os.replace(temporary, BASE/'app.py')
    fd = os.open(BASE, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    print('BOOTSTRAP_ACTIVATED; restart only harpisense-p11.service with operator sudo')


if __name__ == '__main__':
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['prepare','migrate','activate'])
    command = parser.parse_args().command
    {'prepare':prepare,'migrate':migrate_live,'activate':activate}[command]()
