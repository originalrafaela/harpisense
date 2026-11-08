"""Read-only inventory of explicitly named model/runtime artifacts. No secrets."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
WORKSPACE=ROOT.parents[1]


def digest(path):
    result=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):result.update(block)
    return result.hexdigest()


def artifact(path,**metadata):
    if not path.is_file():return {'path':str(path),'present':False,**metadata}
    return {'path':str(path),'present':True,'bytes':path.stat().st_size,'sha256':digest(path),**metadata}


def main():
    lock=json.loads((ROOT/'genai/artifacts.lock.json').read_text(encoding='utf-8'))
    bitnet=WORKSPACE/'harpisense-worktrees/harpia-bitnet/.local-harpia'
    weights=artifact(bitnet/'models'/lock['model']['filename'],kind='bitnet_weights',
        declared_license=lock['model']['license'],pinned_revision=lock['model']['revision'],
        expected_sha256=lock['model']['sha256'],platform='shared-data',packaged=False)
    weights['integrity_matches']=weights.get('sha256')==lock['model']['sha256']
    artifacts=[weights]
    runtime=bitnet/'runtime/BitNet'
    for name in ('llama-cli.exe','llama-server.exe'):
        artifacts.append(artifact(runtime/'build/bin/Release'/name,kind='bitnet_runtime',platform='Windows x64',
            declared_license=lock['runtime']['license'],pinned_revision=lock['runtime']['revision'],
            dependency_portability_verified=False,packaged=False))
    artifacts.append({'kind':'bitnet_runtime','platform':'Ubuntu 24.04 x86_64',
        'present':False,'packaged':False,'status':'linux_binary_not_found_in_scanned_payload'})
    for name in ('LICENSE','LICENSE.txt','3rdparty/llama.cpp/LICENSE'):
        path=runtime/name
        if path.is_file():artifacts.append(artifact(path,kind='runtime_license',platform='shared-data'))
    for name in ('postgres.exe','pg_ctl.exe','initdb.exe'):
        artifacts.append(artifact(Path('D:/Programas/PostgreSQL/bin')/name,kind='development_postgresql_binary',
            platform='Windows x64',packaged_by_this_delivery=False,license_notice_audit='pending'))
    models=[]
    composition=WORKSPACE/'harpisense-worktrees/detection-composition/local-evidence/detection-composition'
    for metadata_file in sorted(composition.glob('*/[ri]f/metadata.json')):
        metadata=json.loads(metadata_file.read_text(encoding='utf-8'))
        document=artifact(metadata_file.parent/'model.joblib',kind=metadata_file.parent.name,
            status='development_synthetic_test_only',approved_for_operational_use=False,packaged=False,
            declared_license=None,metadata_sha256=digest(metadata_file))
        document['model_metadata']={key:metadata[key] for key in (
            'model_version','features','profile','window_seconds','feature_schema_version','versions',
            'classes','threshold','artifact_sha256','dataset_sha256') if key in metadata}
        document['references']=[artifact(p,kind='reference',approved_for_operational_use=False)
            for p in sorted(metadata_file.parent.glob('*reference*.json'))]
        models.append(document)
    source_files=['backend/domain/requirements-scientific.txt','backend/domain/requirements-scientific.lock',
        'backend/domain/harpisense_rf/random_forest.py','backend/domain/harpisense_if/isolation_forest.py',
        'backend/domain/harpisense_xai/shap_library.py','backend/detection_composition/ORIGINS.json',
        'backend/admin_auth/004_first_access.sql','backend/delivery/003_incident_assessment.sql',
        'backend/delivery/004_activity_decision_snapshot.sql','genai/artifacts.lock.json']
    sources=[artifact(ROOT/name,kind='source_or_lock') for name in source_files]
    report={'schema':1,'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'scan_scope':'explicit local development artifact directories; no credential/state/config files scanned',
        'approved_operational_models':[], 'approved_models_identified':False,
        'model_artifacts':models,'runtime_artifacts':artifacts,'sources':sources,
        'offline_installation_verified':{'Windows':False,'Ubuntu':False},
        'ubuntu_installer_network_dependency':{'path':'packaging/native/ubuntu_install.py',
            'operations':['apt-get update','apt-get install python3-venv python3-pip postgresql-16 ca-certificates (and mosquitto in local_managed)'],
            'offline_deb_payload_verified':False},
        'blockers':['APPROVED_RF_IF_ARTIFACT_MANIFEST_MISSING','APPROVED_REFERENCE_TRANSFORM_MANIFEST_MISSING',
            'NATIVE_SCIENTIFIC_WHEELS_PER_PLATFORM_NOT_VALIDATED','BITNET_NOT_IN_NATIVE_PAYLOAD',
            'UBUNTU_BITNET_RUNTIME_MISSING','NATIVE_BITNET_UI_OPERATION_NOT_INTEGRATED',
            'CAPTURE_TO_MODEL_OPERATIONAL_PRODUCERS_NOT_CERTIFIED','CLEAN_OFFLINE_REBOOT_ACCEPTANCE_MISSING']}
    out=ROOT/'docs/evidence/backend-integration-20261107/payload-inventory.json'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print('Inventory written: '+str(out))
    print('Approved operational RF/IF artifacts: 0 identified; BitNet weight integrity match: '+str(weights['integrity_matches']))


if __name__=='__main__':main()
