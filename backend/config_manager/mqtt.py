"""MQTT capability discovery. No probes, service commands or credentials.

An allowed host is policy evidence, never evidence of a live MQTT connection.
Runtime observation/application remain unavailable until real adapters exist.
"""


def mqtt_capabilities(capabilities):
    return {
        'schema_version': '1.0.0',
        'default_mode': 'local_managed',
        'modes': ['local_managed', 'external'],
        'operations': {
            'save_draft': True, 'validate_parameters': True,
            'verify_connection': False, 'apply': False,
            'install_component': False, 'manage_service': False,
            'register_device': False,
        },
        'constraints': {
            'revision': capabilities.revision,
            'hosts': sorted(capabilities.mqtt_hosts),
            'topics': sorted(capabilities.mqtt_topics),
            'ca_refs': sorted(capabilities.ca_refs),
            'tls_modes': ['required'],
            'port_min': 1, 'port_max': 65535,
        },
        'native_installer_responsibilities': ['install_component', 'register_service'],
        'external_server_mutation': False,
    }


def mqtt_status():
    # No runtime observer is installed in this composition. Never infer readiness
    # from a persisted revision, catalog entry, TCP port or setup completion.
    return {
        'schema_version': '1.0.0',
        'component': {'state': 'not_verified', 'observed_at': None},
        'broker': {'state': 'not_verified', 'observed_at': None},
        'consumer': {'state': 'not_verified', 'observed_at': None},
        'devices': [],
        'device_observation': 'not_verified',
        'reason_code': 'MQTT_RUNTIME_OBSERVER_UNAVAILABLE',
    }
