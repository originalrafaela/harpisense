"""Run existing regressions plus batch tests in a local Linux Python container."""
import hashlib
import json
import platform
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'adaptador_logs_p08_p09'))
loader = unittest.TestLoader()
suite = unittest.TestSuite([
    loader.discover(str(ROOT / 'adaptador_logs_p08_p09')),
    unittest.TestLoader().discover(str(ROOT / 'tests'), top_level_dir=str(ROOT / 'tests')),
])
def cases(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite): yield from cases(test)
        else: yield test.id()
names = list(cases(suite))
result = unittest.TextTestRunner(verbosity=2).run(suite)
report = dict(captured_at_utc=datetime.now(timezone.utc).isoformat(),
              synthetic_only=True, python=sys.version, platform=platform.platform(),
              test_cases=names, tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
              code_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted((ROOT / 'adaptador_logs_p08_p09').glob('*.py'))})
(ROOT / 'LOCAL_TEST_RESULTS.json').write_text(json.dumps(report, indent=2) + '\n')
sys.exit(not result.wasSuccessful())
