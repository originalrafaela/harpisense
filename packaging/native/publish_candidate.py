"""Publish only these built, checksummed candidate assets; never print credentials."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import quote

import httpx

ROOT = Path(__file__).resolve().parents[2]
REPO = 'originalrafaela/harpisense'
TAG = 'native-installers-20261106-candidate.2'


def main():
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    remote = subprocess.check_output(['git', 'ls-remote', '--heads', 'origin', 'feat/native-installers'],
                                     cwd=ROOT, text=True).split()[0]
    if head != remote:
        raise SystemExit('PUSH_CANDIDATE_BRANCH_BEFORE_PUBLISHING')
    files = []
    for name in ('HarpiSense-Setup-Windows-x64.exe', 'HarpiSense-Setup-Ubuntu-24.04-x86_64.run'):
        path = ROOT/'dist'/name
        checksum = Path(str(path) + '.sha256')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if checksum.read_text().split()[0] != digest:
            raise SystemExit('ARTIFACT_CHECKSUM_MISMATCH')
        files.extend([path, checksum])
    result = subprocess.run(['git', 'credential', 'fill'],
        input='protocol=https\nhost=github.com\n\n', text=True, capture_output=True,
        env=dict(os.environ, GIT_TERMINAL_PROMPT='0'), cwd=ROOT)
    credentials = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    token = credentials.get('password')
    if not token:
        raise SystemExit('GITHUB_RELEASE_CREDENTIAL_UNAVAILABLE')
    headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
               'X-GitHub-Api-Version': '2022-11-28'}
    body = '''Candidata 2 de instaladores nativos, ainda não homologada em sistemas limpos.

Corrige ausência de harpisense_catalog no payload Ubuntu. Verificação de imports
do runtime distribuído antes da criação/migração do banco em ambas as plataformas.
Windows congelado e Ubuntu/Python 3.12 isolado verificados sem checkout/PYTHONPATH.
Release anterior preservada; não reinstalar sobre a tentativa parcial.

Windows 11 x64: EXE com central, PostgreSQL, Mosquitto local TLS, consumidor e serviços automáticos.
Ubuntu 24.04 x86_64: instalador .run, wheels incluídos; apt requer Internet.

Histórico da candidata 1 (não repetido nesta correção): 23 verificações reais passaram no Windows existente com runtime congelado e processos descartáveis. Nesta candidata foram executados os testes de imports isolados e rejeição de catálogo ausente descritos nas evidências. Instalação completa de serviços e reboot em Windows/Ubuntu limpos ainda NÃO foram testados.

Não instalar sobre o laboratório. O preflight recusa PostgreSQL/Mosquitto/portas/diretórios existentes; reinstalação não substitui dados. Broker local atende loopback nesta candidata. Sensores físicos, captura Linux, RF/IF e contenção não são comprovados pela instalação da central.

Comandos, capacidades e limitações: packaging/native/README.md na branch feat/native-installers.
'''
    api = 'https://api.github.com/repos/' + REPO
    with httpx.Client(headers=headers, timeout=600, follow_redirects=False) as client:
        existing = client.get(api + '/releases/tags/' + TAG)
        if '--refresh-receipt' in sys.argv:
            if existing.status_code != 200 or existing.json()['draft']:
                raise SystemExit('PUBLISHED_RELEASE_REQUIRED')
            output = ROOT/'docs/evidence/native-installers/published-assets.json'
            receipt = json.loads(output.read_text())
            remote_assets = {asset['name']: asset for asset in existing.json()['assets']}
            for asset in receipt['assets']:
                remote_asset = remote_assets[asset['name']]
                if remote_asset['size'] != asset['size'] or remote_asset.get('digest') != 'sha256:' + asset['sha256']:
                    raise SystemExit('PUBLISHED_ASSET_CHECKSUM_MISMATCH')
                asset['download'] = remote_asset['browser_download_url']
            output.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
            print(json.dumps({'release': receipt['release'], 'verified_assets': len(receipt['assets'])}))
            return
        if existing.status_code != 404:
            raise SystemExit('RELEASE_TAG_ALREADY_EXISTS_OR_UNAVAILABLE')
        response = client.post(api + '/releases', json={'tag_name': TAG, 'target_commitish': head,
            'name': 'HarpiSense — instaladores nativos (candidata não homologada)',
            'body': body, 'draft': True, 'prerelease': True, 'make_latest': 'false'})
        if response.status_code != 201:
            raise SystemExit('RELEASE_CREATE_FAILED_HTTP_' + str(response.status_code))
        release = response.json()
        published = []
        for path in files:
            blob = path.read_bytes()
            url = 'https://uploads.github.com/repos/' + REPO + '/releases/' + str(release['id']) + '/assets?name=' + quote(path.name)
            response = client.post(url, content=blob, headers={'Content-Type': 'application/octet-stream',
                                                            'Content-Length': str(len(blob))})
            if response.status_code != 201:
                raise SystemExit('DRAFT_PRESERVED_ASSET_UPLOAD_FAILED_HTTP_' + str(response.status_code))
            asset = response.json()
            digest = hashlib.sha256(blob).hexdigest()
            if asset.get('digest') and asset['digest'] != 'sha256:' + digest:
                raise SystemExit('DRAFT_PRESERVED_REMOTE_CHECKSUM_MISMATCH')
            published.append({'name': path.name, 'size': len(blob), 'sha256': digest,
                              'download': asset['browser_download_url']})
            print(json.dumps({'uploaded': path.name, 'bytes': len(blob)}), flush=True)
        response = client.patch(api + '/releases/' + str(release['id']),
                                json={'draft': False, 'prerelease': True, 'make_latest': 'false'})
        if response.status_code != 200:
            raise SystemExit('DRAFT_PRESERVED_PUBLISH_FAILED_HTTP_' + str(response.status_code))
        receipt = {'branch': 'feat/native-installers', 'commit': head,
                   'release': response.json()['html_url'], 'prerelease': True,
                   'clean_os_installation_approved': False, 'assets': published}
        urls = {asset['name']: asset['browser_download_url'] for asset in response.json()['assets']}
        for asset in published:
            asset['download'] = urls.get(asset['name'], asset['download'])
        output = ROOT/'docs/evidence/native-installers/published-assets.json'
        output.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        print(json.dumps({'release': receipt['release'], 'assets': len(published)}))


if __name__ == '__main__':
    main()
