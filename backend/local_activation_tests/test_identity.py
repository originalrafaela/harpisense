import os
import tempfile
import unittest
from pathlib import Path

from cryptography.fernet import Fernet

from backend.local_activation import (InstallationIdentity, ProtectionError,
                                      WindowsDPAPI, provision_totp_key, load_totp_key)


@unittest.skipUnless(os.name == 'nt', 'native Windows DPAPI test')
class WindowsIdentityTests(unittest.TestCase):
    def test_dpapi_roundtrip_tamper_and_no_plaintext(self):
        protector = WindowsDPAPI()
        secret = os.urandom(32)
        wrapped = protector.protect(secret)
        self.assertNotIn(secret, wrapped)
        self.assertEqual(protector.unprotect(wrapped), secret)
        with self.assertRaises(ProtectionError):
            protector.unprotect(wrapped[:-1] + bytes([wrapped[-1] ^ 1]))

    def test_restart_identity_and_copy_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory)/'one', Path(directory)/'two'
            protector = WindowsDPAPI()
            identity = InstallationIdentity.provision(first, protector)
            public = identity.public_bytes()
            del identity
            loaded = InstallationIdentity.load(first, WindowsDPAPI())
            loaded.prove_possession(public)
            other = InstallationIdentity.provision(second, protector)
            with self.assertRaisesRegex(ProtectionError, 'INSTALLATION_KEY_MISMATCH'):
                other.prove_possession(public)
            with self.assertRaises(FileExistsError):
                InstallationIdentity.provision(first, protector)

    def test_totp_restart_and_type_separation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'totp'
            protector = WindowsDPAPI()
            provision_totp_key(path, protector)
            key = load_totp_key(path, WindowsDPAPI())
            cipher = Fernet(key)
            token = cipher.encrypt(b'fixture-totp-secret')
            self.assertEqual(Fernet(load_totp_key(path, protector)).decrypt(token),
                             b'fixture-totp-secret')
            self.assertNotIn(key, path.read_bytes())
            with self.assertRaisesRegex(ProtectionError, 'INVALID_IDENTITY'):
                InstallationIdentity.load(path, protector)


if __name__ == '__main__':
    unittest.main()
