"""Per-installation Ed25519 identity and an independently wrapped TOTP key."""
import base64
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .protection import ProtectionError, write_new


class InstallationIdentity:
    def __init__(self, key):
        self._key = key

    @classmethod
    def provision(cls, path, protector):
        key = Ed25519PrivateKey.generate()
        raw = key.private_bytes(serialization.Encoding.Raw,
                                serialization.PrivateFormat.Raw,
                                serialization.NoEncryption())
        write_new(path, protector.protect(b'HS-IDENTITY-1\x00' + raw))
        return cls(key)

    @classmethod
    def load(cls, path, protector):
        raw = protector.unprotect(Path(path).read_bytes())
        prefix = b'HS-IDENTITY-1\x00'
        if not raw.startswith(prefix) or len(raw) != len(prefix) + 32:
            raise ProtectionError('INVALID_IDENTITY')
        return cls(Ed25519PrivateKey.from_private_bytes(raw[len(prefix):]))

    def public_bytes(self):
        return self._key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)

    def sign(self, canonical_challenge):
        """Caller must supply the exact contract-defined bytes, after validation."""
        return self._key.sign(canonical_challenge)

    def prove_possession(self, expected_public_key):
        """Fresh in-memory challenge proves the loaded key matches signed binding."""
        import hmac
        import secrets
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        if not hmac.compare_digest(self.public_bytes(), expected_public_key):
            raise ProtectionError('INSTALLATION_KEY_MISMATCH')
        challenge = b'harpisense.offline.possession.v1\x00' + secrets.token_bytes(32)
        Ed25519PublicKey.from_public_bytes(expected_public_key).verify(
            self.sign(challenge), challenge)


def provision_totp_key(path, protector):
    """Returns nothing: plaintext key is only exposed to backend when loaded."""
    write_new(path, protector.protect(b'HS-TOTP-1\x00' + Fernet.generate_key()))


def load_totp_key(path, protector):
    raw = protector.unprotect(Path(path).read_bytes())
    prefix = b'HS-TOTP-1\x00'
    if not raw.startswith(prefix):
        raise ProtectionError('INVALID_TOTP_KEY')
    key = raw[len(prefix):]
    try:
        if len(base64.urlsafe_b64decode(key)) != 32:
            raise ValueError()
        Fernet(key)
    except Exception:
        raise ProtectionError('INVALID_TOTP_KEY') from None
    return key
