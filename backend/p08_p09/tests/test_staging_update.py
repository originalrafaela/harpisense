"""Deployment safeguards exercised on isolated synthetic copies, never staging."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import apply_staging

class TestStagingUpdate(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='SYNTHETIC-staging-update-')
        self.addCleanup(self.temp.cleanup)
        self.target = Path(self.temp.name) / 'target'
        self.candidates = Path(self.temp.name) / 'candidates'
        self.target.mkdir()
        self.candidates.mkdir()
        # Exercise the pinned updater from the validated-batch release, whose
        # candidate hashes are deliberately stable while this branch evolves.
        for name in apply_staging.EXPECTED:
            source = (ROOT / 'tests/fixtures/pinned_staging_pipeline.py'
                      if name == 'p08_p09_pipeline.py'
                      else ROOT / 'adaptador_logs_p08_p09' / name)
            shutil.copy2(source, self.candidates / name)
        for name in apply_staging.DEPENDENCIES:
            # This regression exercises the historical exact-hash updater.
            # Its pinned dependency is intentionally the pre-coverage version.
            source = (ROOT / 'tests/fixtures/previous_log_coverage_integration.py'
                      if name == 'log_coverage_integration.py'
                      else ROOT / 'adaptador_logs_p08_p09' / name)
            shutil.copy2(source, self.target / name)
            shutil.copy2(source, self.candidates / name)
        shutil.copy2(ROOT / 'tests/fixtures/previous_pipeline.py', self.target / 'p08_p09_pipeline.py')
        shutil.copy2(ROOT / 'tests/fixtures/previous_auxiliary_audit_adapter.py', self.target / 'auxiliary_audit_adapter.py')

    def test_dry_run_and_refuse_unexpected_changes(self):
        self.assertFalse(apply_staging.apply(self.target, self.candidates)['applied'])
        self.assertEqual(list(self.target.glob('.validated-batch-backup-*')), [])
        (self.target / 'p08_p09_pipeline.py').write_text('# unexpected concurrent edit')
        with self.assertRaises(ValueError):
            apply_staging.apply(self.target, self.candidates, write=True)
        self.assertEqual((self.target / 'p08_p09_pipeline.py').read_text(), '# unexpected concurrent edit')
        self.assertEqual(list(self.target.glob('.validated-batch-backup-*')), [])

    def test_backup_and_exact_replacement(self):
        receipt = apply_staging.apply(self.target, self.candidates, write=True)
        self.assertTrue(receipt['applied'])
        for name, (old, new) in apply_staging.EXPECTED.items():
            self.assertEqual(apply_staging.digest(self.target / name), new)
            self.assertEqual(apply_staging.digest(Path(receipt['backup_directory']) / name), old)

    def test_failure_restores_both_files(self):
        original_replace = apply_staging.os.replace
        calls = 0
        def fail_once(*args):
            nonlocal calls
            calls += 1
            if calls == 2: raise OSError('SYNTHETIC second replacement failed')
            return original_replace(*args)
        with patch.object(apply_staging.os, 'replace', side_effect=fail_once):
            with self.assertRaises(OSError):
                apply_staging.apply(self.target, self.candidates, write=True)
        for name, (old, _) in apply_staging.EXPECTED.items():
            self.assertEqual(apply_staging.digest(self.target / name), old)
