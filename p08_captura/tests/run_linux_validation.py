"""Regressões sintéticas em Linux; saída JSON em stdout, testes em stderr.

Executar no contêiner com rede desativada, repositório somente leitura e /tmp
efêmero. O instalador é chamado apenas pelos testes com destinos temporários.
"""
import hashlib
import json
import platform
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if platform.system() != "Linux":
    raise SystemExit("Esta validação exige Linux")
sys.path.insert(0, str(ROOT / "backend/p08_p09/adaptador_logs_p08_p09"))
suite = unittest.TestSuite()
for directory in (ROOT / "p08_captura/tests",
                  ROOT / "backend/p08_p09/adaptador_logs_p08_p09",
                  ROOT / "backend/p08_p09/tests"):
    suite.addTests(unittest.TestLoader().discover(str(directory), top_level_dir=str(directory)))

def names(tests):
    for item in tests:
        if isinstance(item, unittest.TestSuite):
            yield from names(item)
        else:
            yield item.id()

cases = list(names(suite))
result = unittest.TextTestRunner(verbosity=2).run(suite)
paths = sorted(set(ROOT.glob("p08_captura/**/*.py")) |
               set(ROOT.glob("backend/p08_p09/**/*.py")))
print(json.dumps({
    "captured_at_utc": datetime.now(timezone.utc).isoformat(),
    "synthetic_only": True, "platform": platform.platform(), "python": sys.version,
    "tests_run": result.testsRun, "test_cases": cases,
    "failures": [{"test": test.id(), "traceback": trace} for test, trace in result.failures],
    "errors": [{"test": test.id(), "traceback": trace} for test, trace in result.errors],
    "vm_actions_executed": False, "capture_started": False,
    "code_sha256": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in paths},
}, indent=2))
raise SystemExit(not result.wasSuccessful())
