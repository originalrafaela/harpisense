"""Compatibility checks; DB presence is a fixture, key crypto uses native DPAPI."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'backend'), str(ROOT/'packaging/native')]
from native_activation import NativeActivationRuntime, load_or_preserve_totp, transport_for
from cryptography.fernet import Fernet
from native_activation import launch_installer_browser


class NativeCompatibility(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows launcher path')
    def test_reopen_completed_and_restart_launch_login_without_ipc_or_cookie(self):
        state = dict(panel_url='http://127.0.0.1:28081')
        for administrator in ('ready', 'migration_required'):
            with patch('native_activation.launcher_administrator_state', return_value=administrator), \
                    patch('native_activation.open_browser') as browser, \
                    patch('local_activation.ipc.request_windows_handoff') as ipc:
                for _ in range(2):
                    launch_installer_browser(state, ROOT)
                self.assertEqual(browser.call_count, 2)
                self.assertIsNone(browser.call_args.args[2])
                ipc.assert_not_called()

    @unittest.skipUnless(os.name == 'nt', 'Windows launcher path')
    def test_first_use_gets_cookie_from_authenticated_ipc(self):
        state = dict(panel_url='http://127.0.0.1:28081',
                     handoff_pipe='fixture-pipe', api_service_sid='fixture-sid')
        for administrator in ('absent', 'mfa_pending'):
            handoff = object()
            with patch('native_activation.launcher_administrator_state', return_value=administrator), \
                    patch('native_activation.open_browser') as browser, \
                    patch('local_activation.ipc.request_windows_handoff', return_value=handoff) as ipc:
                launch_installer_browser(state, ROOT)
                ipc.assert_called_once_with('fixture-pipe', expected_server_sid='fixture-sid')
                self.assertIs(browser.call_args.args[2], handoff)

    def test_existing_admin_without_issuer_configuration_can_restart_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            key = Fernet.generate_key()
            (root/'legacy.key').write_bytes(key)
            state = dict(dsn='fixture-only', panel_url='http://127.0.0.1:28081',
                         key_file=str(root/'legacy.key'))
            with patch('native_activation.existing_administrator', return_value=True):
                for _ in range(2):
                    with NativeActivationRuntime(state, root) as runtime:
                        self.assertEqual(runtime.totp_key, key)
                        self.assertEqual(runtime.adapter.status(None)['administrator'], 'migration_required')
                        self.assertFalse(runtime.adapter.status(None)['first_use_authorized'])
                        self.assertIsNone(runtime.handoff)

    def test_listener_port_comes_from_panel_url(self):
        self.assertEqual(transport_for({'panel_url': 'http://127.0.0.1:28081'}).address,
                         ('127.0.0.1', 28081))
        with self.assertRaises(RuntimeError):
            transport_for({'panel_url': 'http://0.0.0.0:28081'})

    @unittest.skipUnless(os.name == 'nt', 'Native Windows DPAPI required')
    def test_reprotect_preserves_key_and_existing_secret_cipher_across_restart(self):
        from local_activation.protection import WindowsDPAPI
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            key = Fernet.generate_key()
            ciphertext = Fernet(key).encrypt(b'existing-enrolled-totp')
            legacy = directory/'legacy.key'
            legacy.write_bytes(key)
            state = dict(key_file=str(legacy))
            for _ in range(2):
                loaded = load_or_preserve_totp(state, directory, WindowsDPAPI())
                self.assertEqual(loaded, key)
                self.assertEqual(Fernet(loaded).decrypt(ciphertext), b'existing-enrolled-totp')
            self.assertNotIn(key, (directory/'totp.protected').read_bytes())
            legacy.write_bytes(Fernet.generate_key())
            with self.assertRaisesRegex(RuntimeError, 'EXISTING_MFA_KEY_MISMATCH'):
                load_or_preserve_totp(state, directory, WindowsDPAPI())


if __name__ == '__main__':
    unittest.main()
