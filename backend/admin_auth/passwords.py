"""stdlib scrypt: OWASP N=2**17, r=8, p=1, random 128-bit salt."""
import hashlib
import hmac
import secrets
from argon2 import PasswordHasher, Type
from argon2.exceptions import VerifyMismatchError, InvalidHashError, VerificationError

_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16, type=Type.ID)


def password_hash(password):
    return _hasher.hash(password)


def verify(password, encoded):
    if encoded.startswith('$argon2id$'):
        try:
            return _hasher.verify(encoded, password)
        except VerifyMismatchError:
            return False
        except (InvalidHashError, VerificationError):
            raise ValueError('Invalid password verifier') from None
    algorithm, n, r, p, salt, expected = encoded.split('$')
    if (algorithm, n, r, p) != ('scrypt', '131072', '8', '1'):
        raise ValueError('Unsupported password hash version')
    digest = hashlib.scrypt(password.encode('utf-8'), salt=bytes.fromhex(salt),
                            n=int(n), r=int(r), p=int(p), dklen=32,
                            maxmem=256 * 1024 * 1024)
    return hmac.compare_digest(digest, bytes.fromhex(expected))
