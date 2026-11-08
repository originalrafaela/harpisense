"""Read-only inventory and existing capture fixtures; never operate VMs/network.

Developer evidence collector, NOT an installed-product acceptance substitute.
No guest login, VM start/stop, network changes, capture or containment commands.
"""
import ast
import ctypes
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parent
NATIVE = ROOT.parent/'native-installers'
OUT = ROOT/'docs/acceptance/offline'
sys.path.insert(0, str(ROOT))


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4*1024*1024), b''):
            value.update(block)
    return value.hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {'observed_at': datetime.now(timezone.utc).isoformat(),
        'scope': 'source inventory and capture fixtures only',
        'installed_offline_acceptance': False, 'host_network_modified': False,
        'guest_network_modified': False, 'reboot_performed': False,
        'containment_performed': False, 'files': [], 'artifacts': [], 'machines': []}
    paths = ('edge/requirements.txt', 'edge/capture/scapy_gateway.py',
        'edge/capture/offline_pcap.py', 'edge/capture/aggregator.py',
        'edge/capture/backend_client.py', 'backend/delivery/action_review.py',
        'backend/delivery/controls.py', 'backend/native_server/runtime.py',
        'packaging/native/build_windows.py', 'packaging/native/build_ubuntu.py',
        'packaging/native/ubuntu_install.py', 'genai/artifacts.lock.json')
    for name in paths:
        path = ROOT/name
        report['files'].append({'path':name, 'sha256':digest(path)})
    for name in ('build_windows.py', 'build_ubuntu.py', 'ubuntu_install.py'):
        path = NATIVE/'packaging/native'/name
        content = path.read_text(encoding='utf-8')
        report['files'].append({'path':'../native-installers/packaging/native/'+name,
            'sha256':digest(path), 'worktree_content_not_commit_attestation':True})
        if name == 'ubuntu_install.py':
            report['ubuntu_destination_uses_apt_update_install'] = (
                "'apt-get', 'update'" in content and "'apt-get', 'install'" in content)
    for name in ('HarpiSense-Setup-Windows-x64.exe', 'HarpiSense-Setup-Ubuntu-24.04-x86_64.run'):
        path = NATIVE/'dist'/name
        item = {'name':name, 'exists':path.is_file(), 'offline_complete_verified':False}
        if path.is_file():
            item.update(bytes=path.stat().st_size, sha256=digest(path),
                        provenance='existing artifact; not rebuilt or changed')
        report['artifacts'].append(item)
    # Only vmrun list; never expose unrelated lab paths in public evidence.
    vmrun = Path('C:/Program Files (x86)/VMware/VMware Workstation/vmrun.exe')
    running = None
    if vmrun.is_file():
        try:
            result = subprocess.run([str(vmrun), 'list'], capture_output=True, text=True,
                timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                running = {str(Path(line).resolve()).casefold()
                           for line in result.stdout.splitlines()[1:] if line.strip()}
        except (OSError, subprocess.TimeoutExpired):
            pass
    for platform, relative, protected in (
        ('windows11', 'clean-os/windows11/HarpiSense-Clean.vmx', False),
        ('ubuntu2404', 'clean-os/ubuntu2404/HarpiSense-Clean.vmx', False),
        ('ubuntu-candidate3-history', 'candidate2-clean-20261106/Candidate2-Clean.vmx', True),
        ('ubuntu-retest-history', 'ubuntu-clean-retest-20261106/Ubuntu-Clean-Retest.vmx', True)):
        path = NATIVE/'.native-test'/relative
        item = dict(platform=platform, vmx=relative, exists=path.is_file(),
            protected_historical=protected, clean_os_proven=False,
            guest_access_verified=False, offline_lan_verified=False,
            running=None if running is None else str(path.resolve()).casefold() in running)
        if path.is_file():
            content = path.read_text(encoding='utf-8')
            fields = {}
            for line in content.splitlines():
                if '=' in line:
                    key, value = line.split('=', 1)
                    if key.strip() in ('displayName','uuid.bios','guestOS','memsize','ethernet0.connectionType'):
                        fields[key.strip()] = value.strip().strip('"')
            item.update(vmx_sha256=digest(path), identity=fields)
        report['machines'].append(item)
    # Read reference executors as AST only; never import or execute their adapters.
    reference_root = ROOT.parents[1]/'referencias/Versões corretas'
    report['reference_executors'] = []
    for subdir, filename in (
        ('HarpiSense_Defense_Executor_Refatorado_v1', 'defense_executor.py'),
        ('HarpiSense_Gerenciador_Execucao_v1', 'execution_manager.py')):
        path = reference_root/subdir/filename
        if path.is_file():
            tree = ast.parse(path.read_text(encoding='utf-8-sig'))
            imports = sorted({n.module for n in ast.walk(tree)
                              if isinstance(n, ast.ImportFrom) and n.module} |
                             {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names})
            report['reference_executors'].append(dict(path=str(path.relative_to(ROOT.parents[1])),
                sha256=digest(path), imports=imports, deployed=False, executed=False))
    output = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(ROOT/'tests/security'), pattern='test_*.py')
    result = unittest.TextTestRunner(stream=output, verbosity=0).run(suite)
    # Never publish traceback, assertion operands, captured HTTP or fixture credentials.
    report['capture_fixture_tests'] = dict(tests_run=result.testsRun,
        passed=result.wasSuccessful(), failures=len(result.failures), errors=len(result.errors),
        skipped=len(result.skipped), failing_ids=[case.id() for case,_ in result.failures+result.errors],
        live_capture=False, installed_runtime=False)
    target = OUT/'inventory-observed.json'
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({'evidence':str(target.relative_to(ROOT)),
        'capture_tests': report['capture_fixture_tests'],
        'artifacts_observed': sum(a['exists'] for a in report['artifacts']),
        'vm_running_status_available': running is not None}))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
