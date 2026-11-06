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
TAG = 'native-installers-20261106-candidate.4'


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
    body = '''Candidata 4 de instaladores nativos, ainda não homologada em sistemas limpos.

Corrige corrida na instalação Ubuntu: espera limitada pela escuta do broker local
antes de validar MQTT/TLS. Falhas de certificado/autenticação não são repetidas.
O reteste manual da candidata 3 falhou com ConnectionRefusedError, apesar de um
ensaio anterior ter passado. A candidata 3 e todas as evidências são preservadas.

Inclui a correção Backend 6587e009a19bf152060eceeb9c4682ee501f2065:
throttle compatível com sentinela -infinity no PostgreSQL 16.
Candidatas 1 e 2 e suas evidências de falha preservadas.
Esta publicação precede o novo ensaio em VM limpa; não implica aprovação.

Corrige ausência de harpisense_catalog no payload Ubuntu. Verificação de imports
do runtime distribuído antes da criação/migração do banco em ambas as plataformas.
Windows congelado e Ubuntu/Python 3.12 isolado verificados sem checkout/PYTHONPATH.
Release anterior preservada; não reinstalar sobre a tentativa parcial.

Windows 11 x64: EXE com central, PostgreSQL, Mosquitto local TLS, consumidor e serviços automáticos.
Ubuntu 24.04 x86_64: instalador .run, wheels incluídos; apt requer Internet.

Histórico: candidata 1 passou em 23 verificações com processos descartáveis no Windows existente. Candidata 2 passou nos testes de imports isolados, mas falhou no bootstrap PostgreSQL16 em Ubuntu limpo. Esses resultados não aprovam esta candidata 4. A verificação de imports do novo runtime Windows passou durante o build; o ensaio completo desta versão será registrado separadamente.

Não instalar sobre o laboratório. O preflight recusa PostgreSQL/Mosquitto/portas/diretórios existentes; reinstalação não substitui dados. Broker local atende loopback nesta candidata. Sensores físicos, captura Linux, RF/IF e contenção não são comprovados pela instalação da central.

Comandos, capacidades e limitações: packaging/native/README.md na branch feat/native-installers.
'''
    api = 'https://api.github.com/repos/' + REPO
    with httpx.Client(headers=headers, timeout=600, follow_redirects=False) as client:
        existing = client.get(api + '/releases/tags/' + (
            'native-installers-20261106-candidate.3' if '--record-candidate3-retest' in sys.argv else TAG))
        if '--record-candidate3-retest' in sys.argv:
            if existing.status_code != 200 or existing.json()['draft']:
                raise SystemExit('PUBLISHED_RELEASE_REQUIRED')
            note = ('Reteste Ubuntu limpo da candidata 3: FALHOU na instalação.\n'
                    'ConnectionRefusedError na verificação MQTT imediatamente após iniciar serviços.\n'
                    'Broker estava ativo ao inspecionar depois. Corrida de inicialização corrigida\n'
                    'na candidata 4. O ensaio anterior aprovado fica como histórico; não prova\n'
                    'confiabilidade deste instalador. Assets preservados, sem patch na VM.\n'
                    'Evidências: https://github.com/originalrafaela/harpisense/blob/feat/native-installers/'
                    'docs/evidence/native-installers/ubuntu-candidate3-retest-failure/README.md\n')
            previous = existing.json().get('body') or ''
            if note.splitlines()[0] not in previous:
                response = client.patch(api + '/releases/' + str(existing.json()['id']),
                                        json={'body': note + '\n' + previous})
                if response.status_code != 200:
                    raise SystemExit('RELEASE_TRIAL_ANNOTATION_FAILED_HTTP_' + str(response.status_code))
            print(json.dumps({'candidate3_retest': 'failed', 'assets_changed': False}))
            return
        if '--record-clean-trial' in sys.argv:
            if existing.status_code != 200 or existing.json()['draft']:
                raise SystemExit('PUBLISHED_RELEASE_REQUIRED')
            trial = ROOT/'docs/evidence/native-installers/ubuntu-candidate4-trial'
            reports = [json.loads((trial/name).read_text()) for name in
                       ('before-reboot.json', 'after-reboot.json',
                        'before-reboot-browser.json', 'after-reboot-browser.json')]
            passed = all(report['result'] == 'passed' for report in reports)
            outcome = 'APROVADO' if passed else 'NÃO APROVADO'
            note = ('Ensaio Ubuntu limpo da candidata 4: ' + outcome + '.\n'
                    'Resultado exclusivo do Ubuntu; Windows limpo ainda não homologado.\n'
                    'Evidências: https://github.com/originalrafaela/harpisense/tree/feat/native-installers/'
                    'docs/evidence/native-installers/ubuntu-candidate4-trial\n')
            previous = existing.json().get('body') or ''
            if note.splitlines()[0] not in previous:
                response = client.patch(api + '/releases/' + str(existing.json()['id']),
                                        json={'body': note + '\n' + previous})
                if response.status_code != 200:
                    raise SystemExit('RELEASE_TRIAL_ANNOTATION_FAILED_HTTP_' + str(response.status_code))
            print(json.dumps({'release': existing.json()['html_url'], 'clean_trial': 'passed' if passed else 'failed',
                              'assets_changed': False}))
            return
        if '--refresh-receipt' in sys.argv:
            if existing.status_code != 200 or existing.json()['draft']:
                raise SystemExit('PUBLISHED_RELEASE_REQUIRED')
            output = ROOT/'docs/evidence/native-installers/published-assets-candidate4.json'
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
        output = ROOT/'docs/evidence/native-installers/published-assets-candidate4.json'
        output.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        print(json.dumps({'release': receipt['release'], 'assets': len(published)}))


if __name__ == '__main__':
    main()
