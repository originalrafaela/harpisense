"""Exercise the actual Windows impersonation API, pipe ACL and server identity."""
import os
import unittest
import uuid

from backend.local_activation.ipc import WindowsHandoff, request_windows_handoff


@unittest.skipUnless(os.name == 'nt', 'Windows named pipes required')
class WindowsIPCTests(unittest.TestCase):
    def setUp(self):
        import win32api
        import win32security
        token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32security.TOKEN_QUERY)
        try:
            self.sid = win32security.ConvertSidToStringSid(
                win32security.GetTokenInformation(token, win32security.TokenUser)[0])
        finally:
            token.Close()
        self.name = r'\\.\pipe\HarpiSense-Unit-' + uuid.uuid4().hex

    def adapter(self):
        expected = self.sid
        class Adapter:
            _seal = object()
            def _new_session(self, user, capability):
                if user != 'sid:' + expected or capability is not self._seal:
                    raise RuntimeError('UNTRUSTED_IPC')
                return {'authorized_local_peer': True}
        return Adapter()

    def test_real_named_pipe_impersonates_and_checks_local_peer(self):
        server = WindowsHandoff(self.name, self.adapter(), self.sid, [self.sid]).start()
        try:
            self.assertEqual(request_windows_handoff(self.name, expected_server_sid=self.sid),
                             {'authorized_local_peer': True})
        finally:
            server.close()

    def test_acl_access_alone_does_not_authorize_installer_identity(self):
        # The SID can open the service pipe, but is not an authorized installer.
        server = WindowsHandoff(self.name, self.adapter(), self.sid, []).start()
        try:
            with self.assertRaises(Exception):
                request_windows_handoff(self.name, expected_server_sid=self.sid)
        finally:
            server.close()

    def test_client_rejects_a_different_server_identity(self):
        server = WindowsHandoff(self.name, self.adapter(), self.sid, [self.sid]).start()
        try:
            with self.assertRaisesRegex(RuntimeError, 'IPC_SERVER_IDENTITY_MISMATCH'):
                request_windows_handoff(self.name, expected_server_sid='S-1-5-19')
        finally:
            server.close()
