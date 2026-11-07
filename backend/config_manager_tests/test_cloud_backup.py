"""Planning-only contract: no provider SDK/network dependency."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'backend/domain')]
from config_manager.cloud_backup import CLOUD_BACKUP_CATALOG
from config_manager.setup import SETUP_SCHEMA, SetupStore
from config_manager.schema import checked, ConfigError


class CloudBackupTests(unittest.TestCase):
    def test_catalog_never_claims_a_connector(self):
        self.assertEqual({p['id'] for p in CLOUD_BACKUP_CATALOG['providers']},
                         {'s3','azure_blob','gcs','s3_compatible'})
        self.assertTrue(all(not p['implemented'] and not p['tested'] and not p['available']
                            for p in CLOUD_BACKUP_CATALOG['providers']))
        self.assertFalse(any(CLOUD_BACKUP_CATALOG['operations'].values()))

    def test_optional_and_old_documents_are_valid_without_cloud(self):
        for cloud in (None,{'mode':'deferred'}, {'mode':'draft','provider':'azure_blob',
                'destination':'oficina/backup','include':['configuration','inventory'],
                'periodicity':'weekly','retention_days':30}):
            document={'step':'installation','parameters':{}}
            if cloud is not None: document['cloud_backup']=cloud
            checked(document,SETUP_SCHEMA)
            self.assertFalse(any(p['section']=='backup' for p in SetupStore.pending(document)))

    def test_credentials_unknown_provider_and_destination_url_rejected(self):
        for value in ({'mode':'draft','password':'not-a-real-credential'},
                      {'mode':'draft','provider':'unknown'},
                      {'mode':'draft','destination':'https://destination.invalid/?token=example'},
                      {'mode':'draft','retention_days':0}):
            with self.subTest(value=list(value)):
                with self.assertRaises(ConfigError):
                    checked({'step':'backup','parameters':{},'cloud_backup':value},SETUP_SCHEMA)


if __name__=='__main__': unittest.main()
