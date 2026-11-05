"""Ubuntu 24.04 installer. Run only on a clean target, never the TCC VMs."""
import argparse
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import sys

from provision import preflight, create_state, initialize_database, run, prepare_database

APP = Path('/opt/harpisense')
DATA = Path('/var/lib/harpisense')


def unit(name, command, dependencies=()):
    after = 'network-online.target ' + ' '.join(x + '.service' for x in dependencies)
    content = f'''[Unit]
Description=HarpiSense {name}
After={after}
Wants=network-online.target
Requires={' '.join(x + '.service' for x in dependencies)}
[Service]
User=harpisense
Group=harpisense
WorkingDirectory=/opt/harpisense
Environment=PYTHONPATH=/opt/harpisense/backend:/opt/harpisense/backend/domain:/opt/harpisense/genai
ExecStart={command}
Restart=on-failure
RestartSec=5
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/harpisense
[Install]
WantedBy=multi-user.target
'''
    Path('/etc/systemd/system/' + name + '.service').write_text(content)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--payload', required=True, type=Path)
    parser.add_argument('--external-broker', type=Path, help='Private JSON: host/port/username/password/ca_file')
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Use the installer administrative prompt')
    release = Path('/etc/os-release').read_text()
    if 'ID=ubuntu' not in release or 'VERSION_ID="24.04"' not in release:
        raise SystemExit('This first package targets Ubuntu 24.04 x86_64 only')
    mode = 'external' if args.external_broker else 'local_managed'
    preflight(DATA, APP, mode)
    # Inspect before apt; do not adopt pre-existing installations or service users.
    for account in ('harpisense',):
        try:
            pwd.getpwnam(account)
        except KeyError:
            pass
        else:
            raise SystemExit('EXISTING_SERVICE_ACCOUNT')
    external = json.loads(args.external_broker.read_text()) if args.external_broker else None
    run(['apt-get', 'update'])
    # Since preflight rejects existing PostgreSQL/broker configuration, any default
    # services below were installed by this invocation, never third-party services.
    packages = ['python3-venv', 'python3-pip', 'postgresql-16', 'ca-certificates']
    if mode == 'local_managed':
        packages.append('mosquitto')
    run(['apt-get', 'install', '-y'] + packages, env=dict(os.environ, DEBIAN_FRONTEND='noninteractive'))
    run(['systemctl', 'stop', 'postgresql@16-main.service'])
    run(['systemctl', 'disable', 'postgresql.service'])
    if mode == 'local_managed':
        run(['systemctl', 'disable', '--now', 'mosquitto.service'])
    run(['useradd', '--system', '--home', str(DATA), '--shell', '/usr/sbin/nologin', 'harpisense'])
    shutil.copytree(args.payload, APP)
    run(['python3', '-m', 'venv', APP/'venv'])
    run([APP/'venv/bin/pip', 'install', '--no-index', '--find-links', APP/'wheels', '-r', APP/'requirements.lock'])
    # Use the installed application interpreter for database, TLS and auth modules.
    if sys.prefix != str(APP/'venv'):
        os.execve(str(APP/'venv/bin/python'), [str(APP/'venv/bin/python'), str(APP/'packaging/native/ubuntu_install.py'),
            '--finish', str(args.external_broker or '')], dict(os.environ, PYTHONPATH=':'.join(
                str(APP/p) for p in ('backend', 'backend/domain', 'genai', 'packaging/native'))))


def finish(external_path):
    external = json.loads(Path(external_path).read_text()) if external_path else None
    mode = 'external' if external else 'local_managed'
    state = create_state(DATA, mode=mode, external=external)
    run(['chown', '-R', 'harpisense:harpisense', DATA])
    pgdata = DATA/'postgres'
    run(['runuser', '-u', 'harpisense', '--', '/usr/lib/postgresql/16/bin/initdb',
         '-D', pgdata, '-U', 'native_installer', '--encoding=UTF8', '--auth=scram-sha-256',
         '--pwfile', DATA/'pg-init.secret'])
    with (pgdata/'postgresql.conf').open('a') as stream:
        stream.write("\nlisten_addresses = '127.0.0.1'\nport = 15432\nunix_socket_directories = ''\n")
    run(['runuser', '-u', 'harpisense', '--', '/usr/lib/postgresql/16/bin/pg_ctl',
         '-D', pgdata, '-l', DATA/'postgres-prepare.log', '-w', 'start'])
    try:
        initialize_database(state, DATA)
        prepare_database(DATA/'state.json')
    finally:
        run(['runuser', '-u', 'harpisense', '--', '/usr/lib/postgresql/16/bin/pg_ctl', '-D', pgdata, '-w', 'stop'])
    (DATA/'pg-init.secret').rename(DATA/'pg-admin.secret')
    run(['chown', '-R', 'harpisense:harpisense', DATA])
    unit('harpisense-postgres', '/usr/lib/postgresql/16/bin/postgres -D /var/lib/harpisense/postgres')
    broker_deps = ()
    if mode == 'local_managed':
        unit('harpisense-broker', '/usr/sbin/mosquitto -c /var/lib/harpisense/mosquitto.conf')
        broker_deps = ('harpisense-broker',)
    command = '/opt/harpisense/venv/bin/python /opt/harpisense/packaging/native/entry.py '
    unit('harpisense-api', command + 'api --state /var/lib/harpisense/state.json', ('harpisense-postgres',))
    unit('harpisense-mqtt', command + 'consumer --state /var/lib/harpisense/state.json', ('harpisense-postgres',) + broker_deps)
    run(['systemctl', 'daemon-reload'])
    run(['systemctl', 'enable', '--now', 'harpisense-postgres', *broker_deps, 'harpisense-api', 'harpisense-mqtt'])
    from native_server.runtime import probe_broker
    probe_broker(state)
    Path('/usr/share/applications/harpisense.desktop').write_text('''[Desktop Entry]
Type=Application
Name=HarpiSense
Exec=xdg-open http://127.0.0.1:18080
Icon=network-server
Categories=Network;
Terminal=false
''')
    print('HarpiSense instalado. Abra HarpiSense no menu de aplicações: http://127.0.0.1:18080')
    # Local authorized installer console only. Never put grant in URL or logs.
    if sys.stdout.isatty():
        print('Segredo de primeiro acesso (10 minutos):', (DATA/'bootstrap.secret').read_text())
    else:
        print('Grant no arquivo privado /var/lib/harpisense/bootstrap.secret; acesso administrativo local necessário.')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--finish':
        finish(sys.argv[2])
    else:
        main()
