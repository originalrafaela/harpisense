"""stdlib scrypt: OWASP N=2**17, r=8, p=1, random 128-bit salt."""
import hashlib
import hmac
import secrets


def password_hash(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=2**17,
                            r=8, p=1, dklen=32, maxmem=256 * 1024 * 1024)
    return f'scrypt$131072$8$1${salt.hex()}${digest.hex()}'


def verify(password, encoded):
    algorithm, n, r, p, salt, expected = encoded.split('$')
    if (algorithm, n, r, p) != ('scrypt', '131072', '8', '1'):
        raise ValueError('Unsupported password hash version')
    digest = hashlib.scrypt(password.encode('utf-8'), salt=bytes.fromhex(salt),
                            n=int(n), r=int(r), p=int(p), dklen=32,
                            maxmem=256 * 1024 * 1024)
    return hmac.compare_digest(digest, bytes.fromhex(expected))
