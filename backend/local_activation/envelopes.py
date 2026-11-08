"""Strict signed envelopes from INITIAL_AUTH_CONTRACT_V1. No JSON canonicalization."""
import base64
import hashlib
import json
import re

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

LIMIT = 16 * 1024
PURPOSES = {'challenge', 'activation-proof', 'receipt', 'first-use'}


class ActivationError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode('ascii')


def unb64(value, length=None):
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9_-]+', value):
        raise ActivationError('INVALID_ENVELOPE')
    try:
        raw = base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))
    except Exception:
        raise ActivationError('INVALID_ENVELOPE') from None
    if b64(raw) != value or (length is not None and len(raw) != length):
        raise ActivationError('INVALID_ENVELOPE')
    return raw


def key_id(public):
    return hashlib.sha256(public).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ActivationError('INVALID_ENVELOPE')
        result[key] = value
    return result


def parse(raw):
    if not isinstance(raw, (str, bytes)) or len(raw.encode('utf8') if isinstance(raw, str) else raw) > LIMIT:
        raise ActivationError('INVALID_ENVELOPE')
    try:
        return json.loads(raw, object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError):
        raise ActivationError('INVALID_ENVELOPE') from None


def exact(document, fields):
    if type(document) is not dict or set(document) != set(fields):
        raise ActivationError('INVALID_ENVELOPE')
    for name, kind in fields.items():
        if type(document[name]) is not kind:
            raise ActivationError('INVALID_ENVELOPE')
    if document.get('version') != 1:
        raise ActivationError('INVALID_ENVELOPE')


def signed_bytes(purpose, payload):
    if purpose not in PURPOSES:
        raise ActivationError('INVALID_PURPOSE')
    return ('HarpiSense/' + purpose + '/v1\n' + payload).encode('ascii')


def sign(identity, purpose, document):
    payload = b64(json.dumps(document, sort_keys=True, separators=(',', ':'),
                            ensure_ascii=True, allow_nan=False).encode('utf8'))
    result = dict(version=1, key_id=key_id(identity.public_bytes()), payload=payload,
                  signature=b64(identity.sign(signed_bytes(purpose, payload))))
    if len(json.dumps(result).encode('utf8')) > LIMIT:
        raise ActivationError('INVALID_ENVELOPE')
    return result


def verify(envelope, purpose, trusted_keys, fields):
    exact(envelope, dict(version=int, key_id=str, payload=str, signature=str))
    if len(json.dumps(envelope).encode('utf8')) > LIMIT:
        raise ActivationError('INVALID_ENVELOPE')
    public = trusted_keys.get(envelope['key_id'])
    if public is None or len(public) != 32 or key_id(public) != envelope['key_id']:
        raise ActivationError('UNKNOWN_ISSUER')
    payload = unb64(envelope['payload'])
    signature = unb64(envelope['signature'], 64)
    try:
        Ed25519PublicKey.from_public_bytes(public).verify(
            signature, signed_bytes(purpose, envelope['payload']))
    except Exception:
        raise ActivationError('INVALID_SIGNATURE') from None
    document = parse(payload)
    exact(document, fields)
    return document
