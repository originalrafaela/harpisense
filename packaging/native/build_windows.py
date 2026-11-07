"""Build offline setup; source dependencies must be clean redistributable binaries.

Never copy broker configuration/passwords or a PostgreSQL data directory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--postgres-dir', required=True, type=Path)
    parser.add_argument('--mosquitto-dir', required=True, type=Path)
    parser.add_argument('--winsw', required=True, type=Path)
    parser.add_argument('--vc-redist', required=True, type=Path)
    args = parser.parse_args()
    info = ROOT/'.native-build/build_info.json'
    info.parent.mkdir(parents=True,exist_ok=True)
    info.write_text(json.dumps({'package_version': os.environ.get('HARPISENSE_PACKAGE_VERSION','development'),
        'source_commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()}),encoding='utf-8')
    stage = ROOT/('.native-build/payload-' + str(time.time_ns()))
    if not (ROOT/'frontend/dist/index.html').is_file():
        raise SystemExit('Build frontend before packaging')
    common = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
              '--workpath', str(ROOT/'.native-build/pyinstaller'),
              '--specpath', str(ROOT/'.native-build'),
              '--paths', str(ROOT/'backend'), '--paths', str(ROOT/'backend/domain'),
              '--paths', str(ROOT/'genai'), '--paths', str(ROOT/'packaging/native')]
    packages = ['native_server', 'delivery', 'admin_auth', 'config_manager', 'xai_api',
                'harpia', 'harpisense_contracts', 'harpisense_engines', 'uvicorn', 'psycopg', 'psycopg_binary',
                'jsonschema', 'qrcode', 'paho.mqtt', 'detection_composition',
                'harpisense_data','harpisense_rf','harpisense_if','harpisense_xai',
                'shap','sklearn','numpy','pandas','scipy','joblib','numba','llvmlite']
    collect = [item for package in packages for item in ('--collect-all', package)]
    collect += ['--hidden-import', 'harpisense_catalog', '--hidden-import', 'runtime_check']
    data = ['--add-data', str(ROOT/'frontend/dist') + ';frontend/dist',
            '--add-data',str(info)+';native_server']
    for package in ('delivery', 'admin_auth', 'config_manager', 'native_server'):
        for source in (ROOT/'backend'/package).glob('*.sql'):
            data += ['--add-data', str(source) + ';backend/' + package]
            data += ['--add-data', str(source) + ';' + package]
    subprocess.run(common + collect + data + ['--onedir', '--name', 'HarpiSense',
        '--distpath', str(ROOT/'.native-build/runtime'), str(ROOT/'packaging/native/entry.py')], check=True)
    subprocess.run([str(ROOT/'.native-build/runtime/HarpiSense/HarpiSense.exe'), 'check-runtime'],
                   cwd=ROOT.parent, env={k: v for k, v in __import__('os').environ.items()
                                        if k not in ('PYTHONPATH', 'PYTHONHOME')}, check=True)
    stage.mkdir(parents=True)
    shutil.copytree(ROOT/'.native-build/runtime/HarpiSense', stage/'runtime')
    pg = stage/'vendor/postgresql'
    # Only binaries and their supporting distribution files, NEVER data/installer.
    for name in ('bin', 'lib', 'share'):
        shutil.copytree(args.postgres_dir/name, pg/name)
    for name in ('server_license.txt', 'commandlinetools_3rd_party_licenses.txt'):
        shutil.copyfile(args.postgres_dir/name, pg/name)
    mosquitto = stage/'vendor/mosquitto'
    mosquitto.mkdir(parents=True)
    for source in args.mosquitto_dir.iterdir():
        if source.is_file() and (source.suffix.lower() == '.dll' or source.name in
                ('mosquitto.exe', 'mosquitto_pub.exe', 'mosquitto_sub.exe', 'mosquitto_passwd.exe',
                 'edl-v10', 'epl-v20', 'NOTICE.md', 'README.md', 'README-windows.txt')):
            shutil.copyfile(source, mosquitto/source.name)
    shutil.copyfile(args.winsw, stage/'vendor/WinSW-x64.exe')
    shutil.copyfile(args.winsw.with_name('WinSW-LICENSE.txt'), stage/'vendor/WinSW-LICENSE.txt')
    shutil.copyfile(args.vc_redist, stage/'vendor/VC_redist.x64.exe')
    manifest = {'schema': 1, 'application_sources': subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'postgres_version': subprocess.check_output([str(args.postgres_dir/'bin/postgres.exe'), '--version'], text=True).strip(),
        'sources': {'postgres': 'https://www.postgresql.org/download/windows/',
                    'mosquitto': 'https://mosquitto.org/download/',
                    'winsw': 'https://github.com/winsw/winsw/releases/tag/v2.12.0',
                    'vc_redist': 'https://aka.ms/vc14/vc_redist.x64.exe'},
        'files': {str(path.relative_to(stage)).replace('\\', '/'): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in stage.rglob('*') if path.is_file()}}
    (stage/'BUILD-MANIFEST.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    # UAC is requested by the setup executable; installed services are LocalService.
    subprocess.run(common + collect + ['--onefile', '--windowed', '--uac-admin',
        '--name', 'HarpiSense-Setup-Windows-x64', '--distpath', str(ROOT/'dist'),
        '--add-data', str(stage) + ';payload', str(ROOT/'packaging/native/windows_setup.py')], check=True)
    artifact = ROOT/'dist/HarpiSense-Setup-Windows-x64.exe'
    (artifact.with_suffix('.exe.sha256')).write_text(hashlib.sha256(artifact.read_bytes()).hexdigest() + '  ' + artifact.name + '\n')


if __name__ == '__main__':
    main()
