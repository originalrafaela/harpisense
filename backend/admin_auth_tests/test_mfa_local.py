"""Real Linux filesystem controls for the installer helper; no operational DSN."""
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'backend'))
from admin_auth_ops.mfa_local import create_private, private_file


@unittest.skipUnless(os.name == 'posix', 'Linux installer filesystem controls')
class LocalInstallerTests(unittest.TestCase):
    def test_private_file_does_not_overwrite_and_refuses_public_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            path = root/'private.secret'
            create_private(path, b'fixture-only')
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(private_file(path), path)
            with self.assertRaises(FileExistsError):
                create_private(path, b'cannot-overwrite')
            self.assertEqual(path.read_bytes(), b'fixture-only')
            root.chmod(0o755)
            with self.assertRaises(ValueError):
                create_private(root/'refused.secret', b'fixture-only')

    def test_key_reader_refuses_public_file_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            path = root/'private.secret'
            create_private(path, b'fixture-only')
            link = root/'link.secret'
            link.symlink_to(path)
            with self.assertRaises(ValueError):
                private_file(link)
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                private_file(path)

    def test_cli_key_has_no_secret_output_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'mfa.key'
            env = {**os.environ, 'PYTHONPATH': str(ROOT/'backend')}
            command = [sys.executable, '-m', 'admin_auth_ops.mfa_local', 'key', '--key-file', str(path)]
            result = subprocess.run(command, env=env, capture_output=True, check=True)
            self.assertEqual(result.stdout, b'')
            self.assertEqual(result.stderr, b'')
            before = path.read_bytes()
            self.assertEqual(len(before), 44)
            retry = subprocess.run(command, env=env, capture_output=True)
            self.assertNotEqual(retry.returncode, 0)
            self.assertNotIn(before, retry.stdout+retry.stderr)
            self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
