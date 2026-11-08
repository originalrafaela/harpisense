"""Linux-native IPC lifecycle, including actual process death and socket replacement."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest

from backend.local_activation.ipc import UnixHandoff


@unittest.skipUnless(sys.platform == 'linux', 'requires Linux AF_UNIX/SO_PEERCRED/flock')
class UnixLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.path = self.root/'first-use.sock'
        self.servers = []

    def tearDown(self):
        for server in self.servers:
            server.close()
        self.temp.cleanup()

    def start(self):
        server = UnixHandoff(self.path, None, [os.geteuid()]).start()
        self.servers.append(server)
        return server

    def test_actual_crash_leaves_stale_socket_and_restart_recovers(self):
        script = '''import os, sys
from backend.local_activation.ipc import UnixHandoff
UnixHandoff(sys.argv[1], None, [os.geteuid()]).start()
os._exit(71)
'''
        result = subprocess.run([sys.executable, '-c', script, str(self.path)],
                                capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 71, result.stderr.decode())
        self.assertTrue(self.path.is_socket())
        server = self.start()
        self.assertTrue(self.path.is_socket())
        server.close()
        self.assertFalse(self.path.exists())

    def test_active_listener_is_preserved(self):
        first = self.start()
        inode = self.path.stat().st_ino
        with self.assertRaises((BlockingIOError, RuntimeError)):
            self.start()
        self.assertEqual(self.path.stat().st_ino, inode)
        self.assertIsNotNone(first.socket)

    def test_unmanaged_live_listener_is_preserved(self):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as live:
            live.bind(str(self.path))
            self.path.chmod(0o600)
            live.listen(1)
            inode = self.path.stat().st_ino
            with self.assertRaisesRegex(RuntimeError, 'IPC_ENDPOINT_ACTIVE'):
                self.start()
            self.assertEqual(self.path.stat().st_ino, inode)

    def test_close_does_not_unlink_replacement_endpoint(self):
        server = self.start()
        self.path.unlink()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as replacement:
            replacement.bind(str(self.path))
            self.path.chmod(0o600)
            replacement.listen(1)
            inode = self.path.stat().st_ino
            server.close()
            self.assertTrue(self.path.is_socket())
            self.assertEqual(self.path.stat().st_ino, inode)

    def test_regular_file_symlink_and_public_stale_socket_are_refused(self):
        self.path.write_bytes(b'keep')
        with self.assertRaisesRegex(RuntimeError, 'UNSAFE_EXISTING_IPC_ENDPOINT'):
            self.start()
        self.assertEqual(self.path.read_bytes(), b'keep')
        self.path.unlink()
        target = self.root/'target'
        target.write_bytes(b'keep')
        self.path.symlink_to(target)
        with self.assertRaisesRegex(RuntimeError, 'UNSAFE_EXISTING_IPC_ENDPOINT'):
            self.start()
        self.path.unlink()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stale:
            stale.bind(str(self.path))
            self.path.chmod(0o666)
        with self.assertRaisesRegex(RuntimeError, 'UNSAFE_EXISTING_IPC_ENDPOINT'):
            self.start()


if __name__ == '__main__':
    unittest.main()
