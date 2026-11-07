"""Run existing isolated fixtures only; never use a database or OS executor."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'backend/delivery_tests'))
import test_delivery
import test_action_review

suite = unittest.defaultTestLoader.loadTestsFromTestCase(test_delivery.DeliveryTests)
suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(test_action_review.ActionReviewTests))
result = unittest.TextTestRunner(verbosity=2).run(suite)
payload = {
    'source_commit': 'a8fef1f5810ad5077658a29fe2aa407ffd21df6d',
    'environment': 'isolated Python fixtures, memory repository, no PostgreSQL',
    'installed_os_acceptance': False,
    'tests_run': result.testsRun,
    'failures': len(result.failures), 'errors': len(result.errors),
    'skipped': len(result.skipped),
    'passed': result.wasSuccessful(),
    'limits': ['No installed runtime', 'No reboot or service registration',
               'No end-to-end evaluation confirmation or separate approval audit proof',
               'Simulation replay fixture proves one stored result, not OS containment telemetry'],
}
target = ROOT / 'docs/acceptance/security-fixture-result.json'
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8', newline='\n')
raise SystemExit(0 if result.wasSuccessful() else 1)
