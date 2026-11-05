"""Only the new compatibility checks; no rerun of fitting or inference suites."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import unittest

root = Path(__file__).resolve().parents[3]
suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent), pattern='test_*.py')
result = unittest.TextTestRunner(verbosity=2).run(suite)
report = dict(captured_at_utc=datetime.now(timezone.utc).isoformat(),
    tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
    evidence_type='offline packet-format and numeric-contract fixtures only',
    laboratory_capture=False, model_training=False, inference=False, packets_sent=False,
    code_sha256={str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [root/'backend/p08_p09/compatibility_audit.py',
                     *sorted((root/'backend/p08_p09/compatibility_sources').glob('*.py')),
                     Path(__file__), Path(__file__).parent/'test_compatibility_audit.py']})
out = root/'docs/evidence/p08-compatibility-20261105/compatibility-tests.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
sys.exit(not result.wasSuccessful())
