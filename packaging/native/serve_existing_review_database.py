"""Review process only: attach to existing private DB; never provision/reset it."""
import argparse
import hashlib
import os
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/p) for p in ('backend','backend/domain','genai','packaging/native')]


def main():
    import uvicorn
    from native_server.runtime import build_native_api,load_state
    parser=argparse.ArgumentParser();parser.add_argument('--state',required=True,type=Path)
    parser.add_argument('--port',required=True,type=int);args=parser.parse_args()
    state_path=args.state.resolve()
    if not state_path.is_relative_to(ROOT/'.native-test') or args.port not in (18083,18084):
        raise ValueError('REVIEW_SCOPE_REQUIRED')
    state=load_state(state_path)
    app=build_native_api(state,allowed_origins=['http://127.0.0.1:5176','http://127.0.0.1:18083'],
                         runtime_kind='development_candidate_existing_database')
    boot_id=os.environ.get('HARPISENSE_REVIEW_BOOT_ID',str(uuid.uuid4()))
    fingerprints={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in (
        'backend/admin_auth/mfa.py','backend/delivery/linked_cases.py')}
    @app.get('/_review/process-identity',include_in_schema=False)
    def process_identity():
        # Test-runner identity only. No account/session/model/configuration data;
        # this route is NOT registered by the installed native API factory.
        return {'pid':os.getpid(),'boot_id':boot_id,'source_fingerprints':fingerprints}
    uvicorn.run(app,host='127.0.0.1',port=args.port,log_level='critical',access_log=False)


if __name__=='__main__':main()
