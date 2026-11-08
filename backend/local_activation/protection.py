"""OS protection adapters. Never log inputs or fall back to plaintext."""
import ctypes
import os
import stat
from pathlib import Path


class ProtectionError(RuntimeError):
    pass


class WindowsDPAPI:
    """CurrentUser scope: provision and consume under the SAME service identity."""
    def _crypt(self, value, decrypt=False):
        if os.name != 'nt':
            raise ProtectionError('DPAPI_REQUIRES_WINDOWS')

        class Blob(ctypes.Structure):
            _fields_ = [('size', ctypes.c_ulong), ('data', ctypes.POINTER(ctypes.c_ubyte))]

        buffer = ctypes.create_string_buffer(value)
        source = Blob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
        target = Blob()
        crypt = ctypes.WinDLL('crypt32', use_last_error=True)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree.restype = ctypes.c_void_p
        fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
        fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                       ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(Blob)]
        fn.restype = ctypes.c_int
        # UI_FORBIDDEN; no LOCAL_MACHINE scope (would allow other local accounts).
        if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
            raise ProtectionError('DPAPI_FAILED')
        try:
            return ctypes.string_at(target.data, target.size)
        finally:
            kernel.LocalFree(target.data)

    def protect(self, value):
        return self._crypt(value)

    def unprotect(self, value):
        return self._crypt(value, True)


class SystemdCredential:
    """AES wrapping with a key delivered by LoadCredentialEncrypted.

    Provision a 32-byte credential via systemd-creds encrypt --with-key=host,
    passing bytes through stdin. PID 1 decrypts it into the API unit's private
    credential directory. The PostgreSQL unit MUST NOT receive this credential.
    """
    def __init__(self, credential_path):
        if os.name != 'posix':
            raise ProtectionError('SYSTEMD_REQUIRES_LINUX')
        path = Path(credential_path)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
                raise ProtectionError('INSECURE_CREDENTIAL_PERMISSIONS')
            if info.st_uid not in (0, os.geteuid()):
                raise ProtectionError('INSECURE_CREDENTIAL_OWNER')
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                self._key = stream.read(33)
        finally:
            os.close(fd)
        if len(self._key) != 32:
            raise ProtectionError('INVALID_CREDENTIAL_LENGTH')

    def protect(self, value):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        nonce = os.urandom(12)
        return nonce + AESGCM(self._key).encrypt(nonce, value, b'harpisense.local.v1')

    def unprotect(self, value):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        try:
            return AESGCM(self._key).decrypt(value[:12], value[12:], b'harpisense.local.v1')
        except Exception:
            raise ProtectionError('UNPROTECT_FAILED') from None


def write_new(path, data):
    """Parent must already be protected by installer ACLs; never overwrite state."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
