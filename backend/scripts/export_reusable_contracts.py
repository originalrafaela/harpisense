"""Export route schemas without connecting to a database or issuing credentials."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'backend'), str(ROOT/'backend/domain'), str(ROOT/'genai')]
from cryptography.fernet import Fernet
from config_manager.schema import Capabilities
from delivery.app import build_candidate_app


def main():
    os.environ['DATABASE_URL'] = 'postgresql://schema-export@unreachable.invalid/schema_only'
    os.environ['HARPISENSE_ADMIN_USER'] = 'schema-only-technical'
    os.environ['HARPISENSE_ADMIN_PASSWORD'] = 'schema-only-unused-password'
    app = build_candidate_app(installation_id='schema-only',
        capabilities=Capabilities(revision='schema-only'),
        allowed_origins=['https://dashboard.example'], protection_key=Fernet.generate_key(),
        asset_catalog={})
    print(json.dumps(app.openapi(), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
