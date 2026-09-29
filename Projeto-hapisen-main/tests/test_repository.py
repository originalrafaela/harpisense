import json, tomllib, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CASE_DIRS=['00_BASELINE_NORMAL','A03_CONNECTION_FLOOD','A04_PUBLISH_FLOOD','A05_AUTH_BRUTE_FORCE','A06_UNAUTHORIZED_TOPIC','A07_WILDCARD_ABUSE','A08_DEVICE_IMPERSONATION','A09_TELEMETRY_ANOMALY']
class RepoTests(unittest.TestCase):
  def test_case_files(self):
    required={'diagram.json','wokwi.toml','platformio.ini','libraries.txt','README.md'}
    for name in CASE_DIRS:
      p=ROOT/'cases'/name
      self.assertTrue(required.issubset({x.name for x in p.iterdir()}),name)
      self.assertTrue((p/'src/main.cpp').exists(),name)
  def test_json_and_toml(self):
    for name in CASE_DIRS:
      p=ROOT/'cases'/name
      json.loads((p/'diagram.json').read_text())
      with (p/'wokwi.toml').open('rb') as f: cfg=tomllib.load(f)
      self.assertEqual(cfg['wokwi']['version'],1)
      self.assertIn('.pio/build/esp32dev/firmware.bin',cfg['wokwi']['firmware'])
  def test_local_only_target(self):
    for name in CASE_DIRS:
      code=(ROOT/'cases'/name/'src/main.cpp').read_text()
      self.assertIn('host.wokwi.internal',code,name)
      self.assertNotIn('broker.emqx.io',code,name)
  def test_case_metadata(self):
    for name in CASE_DIRS[1:]:
      data=json.loads((ROOT/'cases'/name/'case.json').read_text())
      self.assertRegex(data['id'],r'^A0[3-9]$')
      self.assertEqual(data['safety_scope'],'local_lab_only')
  def test_broker_security(self):
    conf=(ROOT/'broker/config/mosquitto.conf').read_text()
    self.assertIn('allow_anonymous false',conf)
    self.assertIn('acl_file',conf)
    self.assertIn('password_file',conf)
if __name__=='__main__': unittest.main()
