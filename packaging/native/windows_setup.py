"""HarpiSense native Windows setup GUI. Frozen with an offline payload."""
import ctypes
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser
from xml.sax.saxutils import escape

from provision import preflight, create_state, initialize_database, run

PAYLOAD = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))/'payload'
APP = Path(os.environ.get('ProgramFiles', 'C:/Program Files'))/'HarpiSense'
DATA = Path(os.environ.get('ProgramData', 'C:/ProgramData'))/'HarpiSense'


def service(name, executable, arguments, dependencies=()):
    wrapper = APP/(name + '.exe')
    shutil.copyfile(APP/'vendor/WinSW-x64.exe', wrapper)
    xml = f'''<service><id>{name}</id><name>{name}</name>
<description>HarpiSense native central</description>
<executable>{escape(str(executable))}</executable><arguments>{escape(arguments)}</arguments>
<workingdirectory>{escape(str(APP))}</workingdirectory><startmode>Automatic</startmode>
<serviceaccount><username>NT AUTHORITY\\LocalService</username></serviceaccount>
<logpath>{escape(str(DATA/'logs'))}</logpath><log mode="roll-by-size"><sizeThreshold>1024</sizeThreshold><keepFiles>3</keepFiles></log>
<onfailure action="restart" delay="10 sec"/>
{''.join('<depend>' + escape(d) + '</depend>' for d in dependencies)}</service>'''
    wrapper.with_suffix('.xml').write_text(xml, encoding='utf-8')
    run([wrapper, 'install'])
    run([wrapper, 'start'])


def install(mode, external=None):
    if not ctypes.windll.shell32.IsUserAnAdmin():
        raise RuntimeError('ADMINISTRATOR_REQUIRED')
    # No changes at all, including copying application files, until preflight passes.
    preflight(DATA, APP, mode)
    for needed in ('runtime/HarpiSense.exe', 'vendor/postgresql/bin/initdb.exe',
                   'vendor/WinSW-x64.exe', 'vendor/VC_redist.x64.exe') + (('vendor/mosquitto/mosquitto.exe',) if mode == 'local_managed' else ()):
        if not (PAYLOAD/needed).is_file():
            raise RuntimeError('INCOMPLETE_OFFLINE_PAYLOAD:' + needed)
    if mode == 'external':
        # Validate before mutation with the supplied existing identity; no write/publish.
        from native_server.runtime import probe_broker
        probe_broker({'installation_id': 'installer-preflight', 'mqtt': dict(external,
                     topics=['harpisense/poste2/telemetry'])})
    shutil.copytree(PAYLOAD, APP)
    # Offline prerequisite, after preflight; 3010 requests a later reboot.
    import subprocess
    prerequisite = run([APP/'vendor/VC_redist.x64.exe', '/install', '/quiet', '/norestart'], check=False)
    if prerequisite.returncode not in (0, 1638, 3010):
        raise RuntimeError('VC_RUNTIME_INSTALL_FAILED')
    run([APP/'runtime/HarpiSense.exe', 'check-runtime'])
    state = create_state(DATA, mode=mode, external=external)
    (DATA/'logs').mkdir()
    pg = APP/'vendor/postgresql/bin'
    pgdata = DATA/'postgres'
    run([pg/'initdb.exe', '-D', pgdata, '-U', 'native_installer', '--encoding=UTF8',
         '--auth=scram-sha-256', '--pwfile', DATA/'pg-init.secret'])
    with (pgdata/'postgresql.conf').open('a', encoding='utf-8') as stream:
        stream.write("\nlisten_addresses = '127.0.0.1'\nport = 15432\n")
    run(['icacls', pgdata, '/grant', '*S-1-5-19:(OI)(CI)M', '/T', '/Q'])
    # Temporary, installer-owned cluster only. It never uses the existing server.
    run([pg/'pg_ctl.exe', '-D', pgdata, '-l', DATA/'logs/postgres-prepare.log', '-w', 'start'])
    try:
        initialize_database(state, DATA)
        run([APP/'runtime/HarpiSense.exe', 'prepare', '--state', DATA/'state.json'])
    finally:
        run([pg/'pg_ctl.exe', '-D', pgdata, '-w', 'stop', '-m', 'fast'])
    (DATA/'pg-init.secret').rename(DATA/'pg-admin.secret')
    service('HarpiSensePostgres', pg/'postgres.exe', f'-D "{pgdata}"')
    broker_deps = ()
    if mode == 'local_managed':
        service('HarpiSenseBroker', APP/'vendor/mosquitto/mosquitto.exe', f'-c "{DATA / "mosquitto.conf"}"')
        broker_deps = ('HarpiSenseBroker',)
    service('HarpiSenseApi', APP/'runtime/HarpiSense.exe',
            f'api --state "{DATA / "state.json"}"', ('HarpiSensePostgres',))
    service('HarpiSenseMqtt', APP/'runtime/HarpiSense.exe',
            f'consumer --state "{DATA / "state.json"}"', ('HarpiSensePostgres',) + broker_deps)
    run([APP/'runtime/HarpiSense.exe', 'probe', '--state', DATA/'state.json'])
    import urllib.request
    ready = False
    for _ in range(40):
        try:
            with urllib.request.urlopen(state['panel_url'], timeout=2) as response:
                ready = response.status == 200
        except OSError:
            pass
        if ready:
            break
        time.sleep(.5)
    if not ready:
        raise RuntimeError('PANEL_READINESS_FAILED_DATA_PRESERVED')
    programs = Path(os.environ['ProgramData'])/'Microsoft/Windows/Start Menu/Programs'
    (programs/'HarpiSense.url').write_text('[InternetShortcut]\nURL=' + state['panel_url'] + '\n')
    if getattr(sys, 'frozen', False):
        helper = APP/'HarpiSense-FirstAccess.exe'
        shutil.copyfile(sys.executable, helper)
        script = APP/'create-first-access-shortcut.vbs'
        def vbs(value):
            return str(value).replace('"', '""')
        script.write_text('Set s = CreateObject("WScript.Shell")\n' +
            f'Set l = s.CreateShortcut("{vbs(programs / "HarpiSense Primeiro acesso.lnk")}")\n' +
            f'l.TargetPath = "{vbs(helper)}"\nl.Arguments = "--first-access"\nl.Save\n')
        run(['cscript.exe', '//Nologo', script])
        script.unlink()
    return state


def main():
    root = tk.Tk()
    root.title('Instalar HarpiSense')
    root.geometry('660x470')
    if '--first-access' in sys.argv:
        from native_server.runtime import load_state
        from admin_auth.mfa import MFAAdminAuth
        import psycopg
        try:
            state = load_state(DATA/'state.json')
            with psycopg.connect(state['dsn']) as conn:
                present = conn.execute('SELECT 1 FROM hs_admin_account').fetchone()
            if present:
                messagebox.showinfo('HarpiSense', 'A conta administrativa já existe. Use seu login e autenticador.')
                webbrowser.open(state['panel_url'])
                root.destroy()
                return
            grant = MFAAdminAuth(state['dsn'], protection_key=(DATA/'admin-mfa.key').read_bytes()).issue_local_grant()
            # Trusted elevated helper, explicit renewal; never invoked by API startup.
            with (DATA/'bootstrap.secret').open('w', encoding='ascii') as stream:
                stream.write(grant)
            ttk.Label(root, text='Primeiro acesso protegido\nCopie o segredo local no formulário. Validade: 10 minutos.').pack(padx=20, pady=25)
            entry = ttk.Entry(root, width=65)
            entry.insert(0, grant)
            entry.config(state='readonly')
            entry.pack(padx=20)
            ttk.Button(root, text='Abrir painel', command=lambda: webbrowser.open(state['panel_url'])).pack(pady=20)
        except Exception:
            messagebox.showerror('HarpiSense', 'Primeiro acesso indisponível. Verifique os serviços; os dados foram preservados.')
            root.destroy()
            return
        root.mainloop()
        return
    ttk.Label(root, text='HarpiSense — central local', font=('', 18)).pack(pady=15)
    ttk.Label(root, text='Instala PostgreSQL, painel/API e consumidor como serviços automáticos.\nNão instala sensores de captura nem habilita contenção.', justify='left').pack()
    mode = tk.StringVar(value='local_managed')
    ttk.Radiobutton(root, text='Instalar e gerenciar broker local (padrão)', variable=mode, value='local_managed').pack(anchor='w', padx=25, pady=8)
    ttk.Radiobutton(root, text='Usar broker existente (avançado, TLS obrigatório)', variable=mode, value='external').pack(anchor='w', padx=25)
    fields = {}
    form = ttk.Frame(root)
    form.pack(pady=8)
    for row, (name, label, default) in enumerate([('host', 'Servidor', ''), ('port', 'Porta TLS', '8883'),
            ('username', 'Identidade do consumidor existente', ''), ('password', 'Credencial dessa identidade', ''),
            ('ca_file', 'Arquivo CA do broker', '')]):
        ttk.Label(form, text=label).grid(row=row, column=0, sticky='w')
        field = ttk.Entry(form, width=44, show='*' if name == 'password' else '')
        field.insert(0, default)
        field.grid(row=row, column=1)
        fields[name] = field
    def choose_ca():
        value = filedialog.askopenfilename(title='Certificado CA do broker')
        if value:
            fields['ca_file'].delete(0, 'end')
            fields['ca_file'].insert(0, value)
    ttk.Button(root, text='Escolher CA (modo avançado)', command=choose_ca).pack()
    status = tk.StringVar(value='Instalação nova. Se houver conflito, nada será substituído.')
    ttk.Label(root, textvariable=status, wraplength=600).pack(pady=8)
    def start():
        selected = mode.get()
        external = None
        if selected == 'external':
            external = {key: entry.get() for key, entry in fields.items()}
            try:
                external['port'] = int(external['port'])
            except ValueError:
                messagebox.showerror('HarpiSense', 'Porta inválida.')
                return
        button.config(state='disabled')
        status.set('Verificando conflitos e instalando…')
        def worker():
            try:
                state = install(selected, external)
            except Exception as error:
                # Never print a third-party error that may contain submitted secrets.
                code = str(error) if isinstance(error, RuntimeError) else type(error).__name__
                root.after(0, lambda: status.set('Instalação interrompida: ' + code))
                return
            def complete():
                status.set('Serviços iniciados. Abra HarpiSense pelo menu Iniciar nos próximos usos.')
                dialog = tk.Toplevel(root)
                dialog.title('Primeiro acesso protegido — válido por 10 minutos')
                ttk.Label(dialog, text='Copie o segredo local no formulário de criação da conta.\nCadastre o TOTP e guarde os códigos de recuperação.').pack(padx=15, pady=15)
                grant = ttk.Entry(dialog, width=65)
                grant.insert(0, (DATA/'bootstrap.secret').read_text())
                grant.config(state='readonly')
                grant.pack(padx=15)
                ttk.Button(dialog, text='Abrir painel', command=lambda: webbrowser.open(state['panel_url'])).pack(pady=15)
            root.after(0, complete)
        threading.Thread(target=worker, daemon=True).start()
    button = ttk.Button(root, text='Instalar', command=start)
    button.pack(pady=8)
    root.mainloop()


if __name__ == '__main__':
    main()
