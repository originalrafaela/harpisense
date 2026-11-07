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
TAG = 'native-installers-20261106-candidate.5'


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
    body = '''Candidata 5 — consolidação do produto instalável, ainda não homologada em sistemas limpos.

Recuperação de senha com códigos próprios de uso único; não remove MFA nem concede sessão.
Recuperação MFA preservada; orientação para Microsoft Authenticator, sem OAuth Microsoft.
Cadastro permanente de ativos com revisão, auditoria e leitura posterior no PostgreSQL.
Aplicador existente de nome/fuso ligado à composição instalada, com journal e confirmação.
Perfil selecionável antes de aplicar; estado efetivo depende de confirmação do backend.
Executor derivado do modo. Autoridade operacional ausente/vencida ou pendências bloqueiam trocas.
Contenção REAL permanece bloqueada. Entrada de demonstração desativada por padrão.
Runtime instalado expõe versão do pacote e commit na rota autenticada native/status.

Validação com Chromium, HTTP, PostgreSQL e Mosquitto nativos isolados; detalhes e resultados:
https://github.com/originalrafaela/harpisense/blob/feat/native-installers/docs/PRODUCT_CONSOLIDATION_20261106.md

Isso não equivale a instalação/reboot em Windows limpo ou novo aceite Ubuntu.
O aceite Ubuntu da candidata 3 é preservado como histórico, assim como seu reteste com falha.
Produtores autoritativos operacionais, despacho/aprovação/execução reais e aplicação de
configurações MQTT/captura/backup não são substituídos por projeções ou sucesso visual.
Não reinstalar por cima de tentativas ou dados existentes. Releases 1 a 4 preservadas.
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
            trial = ROOT/'docs/evidence/native-installers/ubuntu-candidate5-trial'
            reports = [json.loads((trial/name).read_text()) for name in
                       ('before-reboot.json', 'after-reboot.json',
                        'before-reboot-browser.json', 'after-reboot-browser.json')]
            passed = all(report['result'] == 'passed' for report in reports)
            outcome = 'APROVADO' if passed else 'NÃO APROVADO'
            note = ('Ensaio Ubuntu limpo da candidata 5: ' + outcome + '.\n'
                    'Resultado exclusivo do Ubuntu; Windows limpo ainda não homologado.\n'
                    'Evidências: https://github.com/originalrafaela/harpisense/tree/feat/native-installers/'
                    'docs/evidence/native-installers/ubuntu-candidate5-trial\n')
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
            output = ROOT/'docs/evidence/native-installers/published-assets-candidate5.json'
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
        output = ROOT/'docs/evidence/native-installers/published-assets-candidate5.json'
        output.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        print(json.dumps({'release': receipt['release'], 'assets': len(published)}))


if __name__ == '__main__':
    main()
