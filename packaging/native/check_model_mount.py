"""Check actual product navigation on isolated HTTP/PostgreSQL, without XAI mocks.

Canonical synthetic records from the Backend trial exercise the actual reader.
This never claims statistical or live traffic detector acceptance.
"""
from pathlib import Path
import json
import os
import secrets
import socket
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parents[2]
for part in ('backend','backend/domain','genai','packaging/native'):
    sys.path.insert(0,str(ROOT/part))
import httpx
import pyotp
from playwright.sync_api import sync_playwright,expect
from provision import create_state,initialize_database,prepare_database,run
from delivery.postgres_store import PostgresStore
from delivery.projections import Record
from xai_api.store import XAIStore
from acceptance_product import wait_for


def main():
    private=ROOT/'.native-test'/('model-mount-'+uuid.uuid4().hex)
    evidence_dir=ROOT/'docs/evidence/model-mount-review'
    evidence_dir.mkdir(parents=True,exist_ok=True)
    evidence={'transport':'real native HTTP/PostgreSQL/Chromium','synthetic_incidents':True,
              'xai_backend_integrated':True,'live_traffic':False,'checks':[]}
    def check(value,label):
        if not value: raise AssertionError(label)
        evidence['checks'].append(label)
    for port in (25433,28081):
        with socket.socket() as probe: probe.bind(('127.0.0.1',port))
    state=create_state(private)
    state['dsn']=state['dsn'].replace(':15432/',':25433/')
    state['panel_url']='http://127.0.0.1:28081'
    (private/'state.json').write_text(json.dumps(state),encoding='utf-8')
    pg=Path('D:/Programas/PostgreSQL/bin')
    api=None;pg_started=False;handle=None
    try:
        run([pg/'initdb.exe','-D',private/'postgres','-U','native_installer','--encoding=UTF8',
             '--auth=scram-sha-256','--pwfile',private/'pg-init.secret'])
        with (private/'postgres/postgresql.conf').open('a') as out:
            out.write("\nlisten_addresses='127.0.0.1'\nport=25433\n")
        run([pg/'pg_ctl.exe','-D',private/'postgres','-l',private/'postgres.log','-w','start'])
        pg_started=True
        initialize_database(state,private);prepare_database(private/'state.json')
        store=PostgresStore(state['dsn'])
        records=json.loads((evidence_dir/'synthetic-records.json').read_text(encoding='utf-8-sig'))
        for row in records:
            store.insert(row['kind'],Record(**{k:row[k] for k in ('id','revision','source','data')}))
        reader=XAIStore(store._connect,state['installation_id'],'device_id')
        incident_ids=[r['id'] for r in records if r['kind']=='incident']
        ident=next(i for i in incident_ids if reader.incident(i,1)['state']=='available')
        absent=next(i for i in incident_ids if all(a['state']=='absent' for a in reader.incident(i,1)['analyses']))
        with store._connect() as conn:
            from psycopg.types.json import Jsonb
            conn.execute('INSERT INTO hs_config.asset(installation_id,device_id,revision,document) VALUES (%s,%s,1,%s)',
                         (state['installation_id'],'poste-1',Jsonb({'name':'Poste de ensaio integrado'})))
        check(all(a['asset']['display_name']=='Poste de ensaio integrado' for a in reader.incident(ident,1)['analyses']),
              'reader_uses_existing_native_asset_name')
        handle=(private/'api.log').open('ab')
        env=dict(os.environ,PYTHONPATH=os.pathsep.join(str(ROOT/p) for p in ('backend','backend/domain','genai')))
        api=subprocess.Popen([sys.executable,str(ROOT/'packaging/native/entry.py'),'api','--state',str(private/'state.json')],
                             env=env,stdout=handle,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        http=httpx.Client(base_url=state['panel_url'],trust_env=False,timeout=5)
        wait_for(lambda:http.get('/').status_code==200)
        check(http.get('/p11-api/api/v1/p11/incidents/'+ident+'/explanations?incident_revision=1').status_code==401,
              'reader_requires_admin_session')
        with sync_playwright() as pw:
            browser=pw.chromium.launch()
            page=browser.new_page(viewport={'width':1440,'height':1000})
            page.goto(state['panel_url'])
            page.get_by_role('button',name='Primeira configuração',exact=True).click()
            page.get_by_label('Grant local de uso único',exact=True).fill((private/'bootstrap.secret').read_text())
            page.get_by_label('Usuário',exact=True).fill('model-mount-owner')
            page.get_by_label('Senha da conta administrativa',exact=True).fill(secrets.token_urlsafe(32))
            page.get_by_role('button',name='Criar conta e configurar MFA',exact=True).click()
            page.get_by_role('button',name='Mostrar QR e chave manual',exact=True).click()
            key=page.get_by_label('Chave manual',exact=True).input_value()
            page.get_by_label('Código de 6 dígitos',exact=True).fill(pyotp.TOTP(key).now())
            page.get_by_role('button',name='Confirmar MFA',exact=True).click()
            page.get_by_label('Guardei os códigos em local seguro.').check()
            page.get_by_role('button',name='Concluir e continuar',exact=True).click()
            expect(page.get_by_role('button',name='Sair',exact=True)).to_be_visible()
            expect(page.get_by_text('Sem explicação disponível',exact=False)).to_be_visible()
            page.get_by_label('Incidente selecionado',exact=False).select_option(ident)
            expect(page.get_by_role('button',name='Ver explicação do modelo',exact=True)).to_be_enabled()
            check(True,'dashboard_model_button_available_without_harpia_text')
            with page.expect_request(lambda r:f'/incidents/{ident}/explanations?incident_revision=1' in r.url) as requested:
                page.get_by_role('button',name='Ver explicação do modelo',exact=True).click()
            check(requested.value.method=='GET','authenticated_client_uses_revision_bound_get')
            auth={'Authorization':requested.value.headers['authorization']}
            response=http.get('/p11-api/api/v1/p11/incidents/'+ident+'/explanations?incident_revision=1',headers=auth)
            check(response.status_code==200 and response.headers.get('cache-control')=='no-store'
                  and response.json()['incident_ref']=={'id':ident,'revision':1},'authenticated_envelope_and_no_store')
            check(http.get('/p11-api/api/v1/p11/incidents/'+ident+'/explanations?incident_revision=999',headers=auth).status_code==404,
                  'unknown_incident_revision_is_not_replaced_by_latest')
            expect(page).to_have_url(state['panel_url']+'/#ai')
            expect(page.get_by_label('Incidente da análise do modelo',exact=True)).to_have_value(ident)
            expect(page.get_by_role('tabpanel')).to_be_visible()
            expect(page.get_by_role('heading',name='Características que influenciaram o resultado',exact=True)).to_be_visible()
            check(True,'actual_authenticated_persisted_xai_rendered')
            for detector in ('Random Forest','Isolation Forest'):
                page.get_by_role('tab',name=detector,exact=False).click()
                expect(page.get_by_role('tabpanel',name=detector+' explicação',exact=True)).to_be_visible()
                check(True,detector.lower().replace(' ','_')+'_rendered')
            page.screenshot(path=str(evidence_dir/'model-integrated.png'),full_page=True)
            page.get_by_label('Incidente da análise do modelo',exact=True).select_option(absent)
            page.wait_for_timeout(1000)
            page.screenshot(path=str(evidence_dir/'model-absence.png'),full_page=True)
            expect(page.get_by_text('Explicação não disponível para esta observação.',exact=False)).to_be_visible()
            check(True,'persisted_absence_is_not_fabricated_explanation')
            page.get_by_label('Incidente da análise do modelo',exact=True).select_option(ident)
            expect(page.get_by_role('tabpanel')).to_be_visible()
            page.get_by_role('link',name='Voltar aos incidentes',exact=True).click()
            expect(page.get_by_label('Selecionar incidente',exact=True)).to_have_value(ident)
            expect(page.get_by_role('heading',name='Detalhes do incidente · '+ident,exact=True)).to_be_visible()
            check(True,'incident_selection_preserved_after_ai_return')
            page.get_by_role('link',name='Dashboard',exact=True).click()
            expect(page.get_by_label('Incidente selecionado',exact=False)).to_have_value(ident)
            check(True,'dashboard_selection_preserved_after_detail_return')
            browser.close()
        evidence['result']='passed'
    except Exception as error:
        evidence['result']='failed';evidence['failure_type']=type(error).__name__
        if isinstance(error,AssertionError) and str(error).replace('_','').isalnum():evidence['failure']=str(error)
    finally:
        if api is not None and api.poll() is None: api.terminate();api.wait(15)
        if handle: handle.close()
        if pg_started:run([pg/'pg_ctl.exe','-D',private/'postgres','-w','stop','-m','fast'])
        (evidence_dir/'result.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
        print(json.dumps(evidence,indent=2))
    return 0 if evidence['result']=='passed' else 1


if __name__=='__main__':sys.exit(main())
