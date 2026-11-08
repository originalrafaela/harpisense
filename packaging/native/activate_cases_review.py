"""Upgrade only the owned 18083 development API; preserve PG and other runners."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import uuid

from verify_review_process_restart import metadata,ready,stop

ROOT=Path(__file__).resolve().parents[2]


def main():
    output=ROOT/'docs/evidence/backend-integration-20261107'
    old=json.loads((output/'cases-live.json').read_text(encoding='utf-8'))
    live=json.loads((output/'live-backend.json').read_text(encoding='utf-8'))
    state_path=Path(live['bootstrap_handoff_file']).resolve().parent/'state.json'
    if (old['url']!='http://127.0.0.1:18083' or old['installed'] is not False
            or not old['shares_browser_e2e_database'] or not state_path.is_relative_to(ROOT/'.native-test')):
        raise RuntimeError('OWNED_REVIEW_SCOPE_REQUIRED')
    state=json.loads(state_path.read_text(encoding='utf-8'))
    before,private_before=metadata(state)
    owned_pid=int(old.get('launcher_pid',old['api_pid']))
    # Verify that the PID recorded by our live Popen controller still belongs
    # to the expected Python distribution. Never kill by name or port alone.
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=(wintypes.DWORD,wintypes.BOOL,wintypes.DWORD)
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes=(wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD))
    kernel.CloseHandle.argtypes=(wintypes.HANDLE,)
    handle=kernel.OpenProcess(0x1000,False,owned_pid)
    if not handle:raise RuntimeError('OWNED_API_PID_UNAVAILABLE')
    try:
        buffer=ctypes.create_unicode_buffer(32768);length=wintypes.DWORD(len(buffer))
        if not kernel.QueryFullProcessImageNameW(handle,0,buffer,ctypes.byref(length)):
            raise RuntimeError('API_IMAGE_UNVERIFIED')
        allowed={str(Path(sys.executable).resolve()).casefold(),str((Path(sys.base_prefix)/'python.exe').resolve()).casefold()}
        if buffer.value.casefold() not in allowed:raise RuntimeError('REFUSE_FOREIGN_API_PROCESS')
    finally:kernel.CloseHandle(handle)
    # This Popen tree starts only serve_existing_review_database, never PG.
    # Both 18082 and its database producer/cluster are separate and preserved.
    subprocess.run(['taskkill','/PID',str(owned_pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        with socket.socket() as probe:closed=probe.connect_ex(('127.0.0.1',18083))!=0
        if closed:break
        time.sleep(.05)
    else:raise RuntimeError('OWNED_API_PORT_NOT_RELEASED')
    boot_id=str(uuid.uuid4())
    process=subprocess.Popen([sys.executable,str(ROOT/'packaging/native/serve_existing_review_database.py'),
        '--state',str(state_path),'--port','18083'],cwd=ROOT,
        env=dict(os.environ,HARPISENSE_REVIEW_BOOT_ID=boot_id),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    server_pid=None
    try:
        status,identity=ready(process,18083,boot_id);server_pid=identity['pid']
        after,private_after=metadata(state)
        if before!=after or private_before!=private_after:raise RuntimeError('DATABASE_METADATA_CHANGED')
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        result={'url':old['url'],'allowed_origin':'http://127.0.0.1:5176',
            'unauthenticated_session_http':status,'source_commit':commit,'source_fingerprints':identity['source_fingerprints'],
            'cases_contract_version':2,'shares_browser_e2e_database':True,'provisioning_performed':False,
            'api_pid':server_pid,'launcher_pid':process.pid,'installed':False,'original_runner_preserved':live['url']}
        (output/'cases-live.json').write_text(json.dumps(result,indent=2),encoding='utf-8',newline='\n')
        (output/'cases-process-upgrade.json').write_text(json.dumps({'result':'PASS','old_api_pid':owned_pid,
            'new_api_pid':server_pid,'port_closed_between_processes':closed,'same_database_metadata':True,
            'mfa_secret_unchanged':True,'setup_draft_unchanged':True,'database_metadata':after,
            'source_commit':commit,'installed':False,'os_reboot_tested':False},indent=2),encoding='utf-8',newline='\n')
        print(json.dumps(result),flush=True)
        process.wait()
    finally:stop(process,server_pid)


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'result':'BLOCKED','code':str(error) if isinstance(error,RuntimeError) else type(error).__name__}),flush=True)
        raise SystemExit(1)
