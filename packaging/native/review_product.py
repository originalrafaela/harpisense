"""Keep the actual product UI available for a local design review.

Disposable native PostgreSQL, canonical synthetic inputs, existing authentication.
Not a clean-machine installation or operational containment acceptance.
"""
from pathlib import Path
import json
import os
import secrets
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[2]
for path in ('backend','backend/domain','genai','packaging/native'):
    sys.path.insert(0,str(ROOT/path))
import httpx
import pyotp
from playwright.sync_api import sync_playwright, expect
from provision import create_state, initialize_database, prepare_database, run
from delivery.postgres_store import PostgresStore
from delivery.projections import Record
from acceptance_product import wait_for


def main():
    private=ROOT/'.native-test'/('product-review-'+uuid.uuid4().hex)
    pg=Path('D:/Programas/PostgreSQL/bin')
    state=create_state(private)
    state['dsn']=state['dsn'].replace(':15432/',':25434/')
    state['panel_url']='http://127.0.0.1:28082'
    (private/'state.json').write_text(json.dumps(state),encoding='utf-8')
    manifest=ROOT/'.native-build/product-review.json'
    api=None;started=False;log=None
    try:
        run([pg/'initdb.exe','-D',private/'postgres','-U','native_installer','--encoding=UTF8',
             '--auth=scram-sha-256','--pwfile',private/'pg-init.secret'])
        with (private/'postgres/postgresql.conf').open('a') as stream:
            stream.write("\nlisten_addresses='127.0.0.1'\nport=25434\n")
        run([pg/'pg_ctl.exe','-D',private/'postgres','-l',private/'postgres.log','-w','start'])
        started=True
        initialize_database(state,private);prepare_database(private/'state.json')
        store=PostgresStore(state['dsn'])
        records=json.loads((ROOT/'docs/evidence/model-mount-review/synthetic-records.json').read_text())
        for row in records:
            store.insert(row['kind'],Record(**{k:row[k] for k in ('id','revision','source','data')}))
        env=dict(os.environ,PYTHONPATH=os.pathsep.join(str(ROOT/p) for p in ('backend','backend/domain','genai')))
        log=(private/'api.log').open('ab')
        api=subprocess.Popen([sys.executable,str(ROOT/'packaging/native/entry.py'),'api','--state',str(private/'state.json')],
            env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        client=httpx.Client(base_url=state['panel_url'],trust_env=False,timeout=5)
        wait_for(lambda:client.get('/').status_code==200)
        branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=False)
            page=browser.new_page(viewport={'width':1440,'height':1000})
            page.goto(state['panel_url'])
            page.get_by_role('button',name='Primeira configuração',exact=True).click()
            page.get_by_label('Grant local de uso único',exact=True).fill((private/'bootstrap.secret').read_text())
            page.get_by_label('Usuário',exact=True).fill('revisao-design')
            page.get_by_label('Senha da conta administrativa',exact=True).fill(secrets.token_urlsafe(32))
            page.get_by_role('button',name='Criar conta e configurar MFA',exact=True).click()
            page.get_by_role('button',name='Mostrar QR e chave manual',exact=True).click()
            key=page.get_by_label('Chave manual',exact=True).input_value()
            page.get_by_label('Código de 6 dígitos',exact=True).fill(pyotp.TOTP(key).now())
            page.get_by_role('button',name='Confirmar MFA',exact=True).click()
            page.get_by_label('Guardei os códigos em local seguro.').check()
            page.get_by_role('button',name='Concluir e continuar',exact=True).click()
            expect(page.get_by_role('button',name='Sair',exact=True)).to_be_visible()
            manifest.write_text(json.dumps(dict(url=state['panel_url'],branch=branch,commit=commit,
                pid=os.getpid(),private=str(private),api_pid=api.pid,authenticated_window=True,
                backend='native HTTP/PostgreSQL',inputs='synthetic canonical records',docker=False,
                clean_machine_acceptance=False),indent=2),encoding='utf-8')
            while not (private/'stop-review').exists() and browser.is_connected():
                page.wait_for_timeout(1000)
            browser.close()
    finally:
        if api is not None and api.poll() is None:api.terminate();api.wait(15)
        if log:log.close()
        if started:run([pg/'pg_ctl.exe','-D',private/'postgres','-w','stop','-m','fast'])


if __name__=='__main__':main()
