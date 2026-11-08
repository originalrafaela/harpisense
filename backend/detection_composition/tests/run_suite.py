"""Reproducible local acceptance report, separate from historical P08 results."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import subprocess
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]
suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent), pattern='test_*.py')
result = unittest.TextTestRunner(verbosity=2).run(suite)
regressions = []
out = ROOT/'docs/evidence/detection-composition-20261104'
out.mkdir(parents=True, exist_ok=True)
for name, directory in [('p08-adapters', 'backend/p08_p09/adaptador_logs_p08_p09'),
                         ('p08-batch', 'backend/p08_p09/tests')]:
    command = [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', directory, '-v']
    completed = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)
    output = completed.stdout + completed.stderr
    (out/(name+'.txt')).write_text(output)
    match = re.search(r'Ran (\d+) tests?', output)
    regressions.append(dict(name=name, tests_run=int(match[1]) if match else None,
                            returncode=completed.returncode, evidence='synthetic contract fixtures'))
    print(name+': '+('OK' if completed.returncode == 0 else 'FAILED'), flush=True)
report = dict(captured_at_utc=datetime.now(timezone.utc).isoformat(),
              tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
              inference='real sklearn estimators fitted/calibrated on explicit synthetic data',
              database='disposable PostgreSQL 18.6', api='P11 TestClient with real PostgreSQL store',
              laboratory_validated=False, statistical_validation=False, vm_validated=False,
              execution_performed=False,
              regressions=regressions,
              code_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted((ROOT/'backend/detection_composition').rglob('*.py'))})
(out/'test-results.json').write_text(json.dumps(report, indent=2)+'\n')
sys.exit(not result.wasSuccessful() or any(r['returncode'] for r in regressions))
