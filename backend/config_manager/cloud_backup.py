"""Planning catalog only: no SDK, credentials, account or network operation."""
PROVIDERS = (('s3', 'Amazon S3'), ('azure_blob', 'Azure Blob Storage'),
             ('gcs', 'Google Cloud Storage'), ('s3_compatible', 'Compatível com a API S3'))
CLOUD_BACKUP_CATALOG = {
    'schema_version': '1.0.0',
    'providers': [{'id': identifier, 'label': label, 'connector_status': 'planned',
                   'implemented': False, 'tested': False, 'available': False}
                  for identifier, label in PROVIDERS],
    'operations': {'connect': False, 'run': False, 'restore': False, 'schedule': False},
    'configuration_state': 'not_configured',
    'last_execution': None, 'last_verified_restore': None,
}
