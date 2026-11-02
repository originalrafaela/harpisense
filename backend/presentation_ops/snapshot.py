"""Snapshot and isolated restore rehearsal; never restore the operational database.

Run as the existing service account. Credentials stay in process environment.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from datetime import datetime, timezone

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

BASE = Path('/opt/harpisense/staging/p11-postgresql')
PG = Path('/usr/lib/postgresql/18/bin')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(argv, **kw):
    result = subprocess.run([str(x) for x in argv], capture_output=True, **kw)
    if result.returncode:
        raise RuntimeError('Command failed (details retained privately): ' + str(argv[0]))
    return result


def receipt(conn):
    conn.execute("SET LOCAL TIME ZONE 'UTC'")
    tables = conn.execute("SELECT schemaname,tablename FROM pg_tables WHERE schemaname IN ('public','hs_config') ORDER BY 1,2").fetchall()
    result = {}
    for schema, table in tables:
        query = sql.SQL("SELECT count(*),md5(COALESCE(string_agg(v,'' ORDER BY v),'')) FROM (SELECT md5(row_to_json(t)::text) v FROM {}.{} t) s").format(sql.Identifier(schema), sql.Identifier(table))
        count, digest = conn.execute(query).fetchone()
        result[schema+'.'+table] = {'count': count, 'digest': digest}
    return result


def main():
    os.umask(0o077)
    values = dict(line.split('=', 1) for line in (BASE/'.env').read_text().splitlines()
                  if '=' in line and not line.startswith('#'))
    dsn = values['HARPISENSE_DATABASE_URL']
    destination = BASE/'.presentation-backups'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    destination.mkdir(parents=True, mode=0o700)
    saved = destination/'files'
    saved.mkdir(mode=0o700)
    paths = [BASE/'app.py', BASE/'postgres_store.py', BASE/'mqtt_consumer.py',
             BASE/'harpia_deterministic', BASE/'.env', BASE/'.mqtt_password',
             BASE/'.admin-auth-releases/admin-session-20261030-r1',
             Path('/etc/systemd/system/harpisense-p11.service')]
    presentation = BASE/'presentation-state'
    if presentation.exists():
        paths.append(presentation)
    manifest = {}
    for index, path in enumerate(paths):
        if not path.exists():
            continue
        target = saved/str(index)
        if path.is_dir():
            shutil.copytree(path, target)
        else:
            shutil.copy2(path, target)
        for source in ([path] if path.is_file() else sorted(p for p in path.rglob('*') if p.is_file())):
            relative = Path(str(index)) if path.is_file() else Path(str(index))/source.relative_to(path)
            stat = source.stat()
            manifest[str(source)] = dict(copy=str(relative), sha256=sha(source),
                                        uid=stat.st_uid, gid=stat.st_gid, mode=stat.st_mode & 0o777)
    parameters = conninfo_to_dict(dsn)
    env = dict(os.environ)
    for key, name in [('host','PGHOST'),('port','PGPORT'),('user','PGUSER'),
                      ('password','PGPASSWORD'),('dbname','PGDATABASE'),('sslmode','PGSSLMODE')]:
        if key in parameters:
            env[name] = parameters[key]
    dump = destination/'database.dump'
    with psycopg.connect(dsn) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        # No registry is installed yet: refuse to claim a coordinated live snapshot otherwise.
        if conn.execute("SELECT to_regclass('hs_config.installation')").fetchone()[0]:
            raise RuntimeError('Registry exists: coordinate application writes before snapshot')
        original = receipt(conn)
        snapshot = conn.execute('SELECT pg_export_snapshot()').fetchone()[0]
        run(['/usr/bin/pg_dump','--format=custom','--snapshot',snapshot,'--file',dump], env=env)
    metadata = dict(created_at=datetime.now(timezone.utc).isoformat(), dump_sha256=sha(dump),
                    tables=original, files=manifest, registry='absent',
                    presentation_directory='absent' if not presentation.exists() else str(presentation))
    (destination/'backup.json').write_text(json.dumps(metadata, indent=2))
    # Restore files into a second directory; compare all bytes without touching originals.
    restored_files = destination/'restore-files'
    shutil.copytree(saved, restored_files)
    for entry in manifest.values():
        assert sha(restored_files/entry['copy']) == entry['sha256']
    cluster = destination/'isolated-postgres'
    socket = destination/'socket'
    socket.mkdir(mode=0o700)
    run([PG/'initdb','-D',cluster,'--auth-local=trust','--auth-host=reject','--no-locale','--encoding=UTF8'])
    started = False
    try:
        # Unix socket in a private directory only. No TCP listener; no operational DSN.
        run([PG/'pg_ctl','-D',cluster,'-l',destination/'isolated-postgres.log',
             '-o',"-c listen_addresses='' -c unix_socket_directories="+str(socket)+' -p 55449','-w','start'])
        started = True
        isolated = dict(host=str(socket), port=55449, user='harpiserver', dbname='postgres')
        with psycopg.connect(**isolated, autocommit=True) as conn:
            conn.execute('CREATE DATABASE presentation_restore')
        isolated['dbname'] = 'presentation_restore'
        clean = {k:v for k,v in os.environ.items() if not k.startswith('PG')}
        run(['/usr/bin/pg_restore','--exit-on-error','--no-owner','--no-acl',
             '--host',socket,'--port','55449','--username','harpiserver',
             '--dbname','presentation_restore',dump], env=clean)
        with psycopg.connect(**isolated) as conn:
            conn.execute('SET TRANSACTION READ ONLY')
            restored = receipt(conn)
        assert original == restored, 'Restored table digests differ'
        verified = dict(backup=str(destination), dump_sha256=sha(dump),
                        all_table_digests_match=True, files_match=True,
                        restored_tables=restored, restore_owner='isolated operator; original ownership in backup',
                        tcp_listener=False, operational_database_restored=False)
        (destination/'restore-verified.json').write_text(json.dumps(verified, indent=2))
    finally:
        if started:
            run([PG/'pg_ctl','-D',cluster,'-m','fast','-w','stop'])
    print(json.dumps(verified))


if __name__ == '__main__':
    main()
