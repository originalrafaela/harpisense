"""Contract v1 exact-byte Ed25519 envelopes; no canonicalization on verify."""
import base64
import hashlib
import json
import re
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from cryptography.exceptions import InvalidSignature


def encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode('ascii')


def decode(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', value):
        raise ValueError('Invalid encoding')
    raw = base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))
    if encode(raw) != value:
        raise ValueError('Invalid encoding')
    return raw


def key_id(key):
    raw = key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    return hashlib.sha256(raw).hexdigest()


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('Duplicate key')
        result[key] = value
    return result


def loads(raw):
    if len(raw) > 16384:
        raise ValueError('Document too large')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: invalid())


def invalid():
    raise ValueError('Invalid document')


def sign(private, purpose, document):
    payload = encode(json.dumps(document, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('utf-8'))
    message = ('HarpiSense/' + purpose + '/v1\n' + payload).encode('ascii')
    return dict(version=1, key_id=key_id(private.public_key()), payload=payload, signature=encode(private.sign(message)))


def verify(envelope, purpose, keys, fields):
    if (not isinstance(envelope, dict) or set(envelope) != {'version','key_id','payload','signature'}
            or type(envelope['version']) is not int or envelope['version'] != 1):
        raise ValueError('Invalid envelope')
    if len(json.dumps(envelope)) > 16384 or not isinstance(envelope['key_id'], str):
        raise ValueError('Invalid envelope')
    key = keys.get(envelope['key_id'])
    if key is None or key_id(key) != envelope['key_id']:
        raise ValueError('Unknown key')
    payload = decode(envelope['payload'])
    try:
        key.verify(decode(envelope['signature']), ('HarpiSense/' + purpose + '/v1\n' + envelope['payload']).encode('ascii'))
    except InvalidSignature:
        raise ValueError('Invalid signature') from None
    document = loads(payload.decode('utf-8'))
    if not isinstance(document, dict) or set(document) != set(fields):
        raise ValueError('Invalid document')
    for field in fields:
        if field in ('version', 'issued_at', 'expires_at', 'activated_at'):
            if type(document[field]) is not int:
                raise ValueError('Invalid integer')
        elif not isinstance(document[field], str):
            raise ValueError('Invalid string')
    if document['version'] != 1:
        raise ValueError('Invalid version')
    return document


def public(value):
    return Ed25519PublicKey.from_public_bytes(decode(value))
