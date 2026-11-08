"""Build-time inputs from the distributor. No fixture or generated trust fallback."""
import json
from pathlib import Path
import shutil
from urllib.parse import urlsplit
import base64
import hashlib


def add_arguments(parser):
    parser.add_argument('--activation-config', type=Path, required=True,
                        help='Distributor JSON: real HTTPS issuer_url and issuer_keys raw32 base64url map')
    parser.add_argument('--activation-key-file', type=Path, required=True,
                        help='Private delivery input: issued activation key, never issuer signing key')
    parser.add_argument('--chromium-dir', type=Path, required=True,
                        help='Offline Chromium distribution matching the pinned Playwright version')


def stage_activation(args, stage, *, windows):
    cfg = json.loads(args.activation_config.read_text())
    if set(cfg) != {'issuer_url', 'issuer_keys'}:
        raise RuntimeError('INVALID_DISTRIBUTOR_CONFIGURATION')
    url = urlsplit(cfg['issuer_url'])
    if url.scheme != 'https' or not url.hostname or url.hostname.endswith(('.invalid', '.example')):
        raise RuntimeError('REAL_HTTPS_ISSUER_REQUIRED')
    if url.username or url.password or url.query or url.fragment or url.path not in ('', '/'):
        raise RuntimeError('INVALID_DISTRIBUTOR_CONFIGURATION')
    if not cfg['issuer_keys']:
        raise RuntimeError('DISTRIBUTOR_TRUST_BUNDLE_REQUIRED')
    for name, value in cfg['issuer_keys'].items():
        public = base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))
        if len(public) != 32 or hashlib.sha256(public).hexdigest() != name:
            raise RuntimeError('INVALID_DISTRIBUTOR_TRUST_KEY')
    license_key = args.activation_key_file.read_text(encoding='ascii').strip()
    raw = base64.urlsafe_b64decode(license_key + '=' * (-len(license_key) % 4))
    if len(license_key) != 43 or len(raw) != 32 or base64.urlsafe_b64encode(raw).rstrip(b'=').decode() != license_key:
        raise RuntimeError('INVALID_DELIVERY_LICENSE')
    executable = args.chromium_dir/('chrome.exe' if windows else 'chrome')
    if not executable.is_file():
        raise RuntimeError('OFFLINE_CHROMIUM_REQUIRED')
    shutil.copytree(args.chromium_dir, stage/'browser')
    (stage/'native-activation.json').write_text(json.dumps(cfg), encoding='ascii')
    (stage/'delivery-license.secret').write_text(license_key, encoding='ascii')
