"""Packet-format fixtures; separate from the original standard-library gate suite."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

from harpisense_data.windows import FEATURES, SCHEMA_VERSION, versions
from harpisense_data.preparar_eventos import aggregate as p09_aggregate
from p08_p09.compatibility_audit import audit, inspect_pcap, model_requirements, read_json, verified_sources
from p08_p09.compatibility_sources.pcap_to_events import ConversionError


def frame(sport, dport, flags, payload=b''):
    ethernet = bytes.fromhex('00112233445566778899aabb0800')
    ip = bytearray(20)
    ip[0] = 0x45; ip[8] = 64; ip[9] = 6
    struct.pack_into('!H', ip, 2, 40+len(payload))
    ip[12:16] = bytes([192, 0, 2, 10]); ip[16:20] = bytes([192, 0, 2, 20])
    tcp = bytearray(20)
    struct.pack_into('!HH', tcp, 0, sport, dport)
    tcp[12] = 0x50; tcp[13] = flags
    return ethernet+ip+tcp+payload


def pcap(path, records, *, linktype=1, truncated=False):
    data = b'\xd4\xc3\xb2\xa1'+struct.pack('<HHiIII', 2, 4, 0, 0, 65535, linktype)
    for stamp, packet in records:
        second = int(stamp); fraction = round((stamp-second)*1000000)
        original_len = len(packet)+(1 if truncated else 0)
        data += struct.pack('<IIII', second, fraction, len(packet), original_len)+packet
    path.write_bytes(data)


class CompatibilityAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'fixture.pcap'
        self.start = int(datetime(2026, 11, 5, 2, tzinfo=timezone.utc).timestamp())
        self.profile = dict(profile_id='DECLARED-CONTRACT-FIXTURE', traffic_profile='tcp-observacao',
            sensor_id='fixture-endpoint', interface='ens33', source_ip='192.0.2.10', destination_ip='192.0.2.20',
            required_sources=[dict(source=source, kind='gateway_capture' if source=='gateway_capture' else 'signed_log_bundle',
                                   host_id='fixture-only') for source in ('gateway_capture','mqtt_broker','mqtt_consumer','api_fastapi')])
        self.session = dict(session_id='DECLARED-CONTRACT-FIXTURE',
            capture_effective_started_at='2026-11-05T02:00:00Z', capture_effective_ended_at='2026-11-05T02:00:10Z')
        pcap(self.path, [(self.start+1, frame(40000,1883,2)),
                        (self.start+1.5, frame(40000,1883,2)),
                        (self.start+2, frame(40000,1883,16,b'0123456789')),
                        (self.start+3, frame(40001,1884,4))])

    def test_deployed_p08_features_match_official_p09_and_keep_legacy_id(self):
        convert, _, _ = verified_sources()
        result, diagnostic = inspect_pcap(self.path, self.session, self.profile)
        row = result['windows'][0]
        events, stats = convert(self.path, self.profile['sensor_id'], self.profile['interface'])
        official = p09_aggregate(events, session=self.session['session_id'], profile=self.profile['traffic_profile'],
            interface='ens33', destination=self.profile['destination_ip'], window_identity_version='harpisense.window.v2')
        for name in FEATURES:
            self.assertAlmostEqual(row[name], official.iloc[0][name])
        self.assertEqual(row['bytes_total'], 170)  # IP lengths, excluding four Ethernet headers.
        self.assertEqual(row['packet_count'], 4)
        self.assertEqual(row['syn_count'], 2)
        self.assertEqual(row['connections_per_second'], .1)  # SYN retransmission is not a new tuple.
        self.assertTrue(diagnostic['windows'][0]['legacy_edge_id_matches'])
        self.assertEqual(diagnostic['windows'][0]['canonical_v2_alias'], official.iloc[0]['window_id'])
        self.assertNotEqual(row['window_id'], official.iloc[0]['window_id'])
        self.assertFalse(result['ready_for_inference'])
        self.assertEqual(stats['rejected'], 0)

    def test_partial_window_is_not_promoted_to_complete(self):
        _, diagnostic = inspect_pcap(self.path, {**self.session, 'capture_effective_started_at':'2026-11-05T02:00:00.5Z'}, self.profile)
        self.assertTrue(diagnostic['windows'][0]['partial_window'])

    def test_unsupported_link_layer_pcapng_and_truncation_fail(self):
        convert, _, _ = verified_sources()
        for linktype, truncated in [(113, False), (1, True)]:
            pcap(self.path, [(self.start+1,frame(40000,1883,2))], linktype=linktype, truncated=truncated)
            with self.assertRaises(ConversionError):
                convert(self.path, 'fixture', 'ens33')
        self.path.write_bytes(b'\x0a\x0d\x0d\x0a'+b'0'*40)
        with self.assertRaises(ConversionError):
            convert(self.path, 'fixture', 'ens33')

    def test_vlan_record_is_explicitly_rejected_not_converted_or_zero_filled(self):
        convert, _, _ = verified_sources()
        packet = frame(40000,1883,2)
        packet = packet[:12]+bytes.fromhex('810000000800')+packet[14:]
        pcap(self.path, [(self.start+1, packet)])
        events, stats = convert(self.path, 'fixture', 'ens33')
        self.assertEqual(events, [])
        self.assertEqual(stats['rejected'], 1)

    def metadata(self, features=None):
        artifact = Path(self.temp.name)/'model.joblib'
        artifact.write_bytes(b'CONTRACT HASH FIXTURE ONLY - NEVER DESERIALIZED')
        pin = hashlib.sha256(artifact.read_bytes()).hexdigest()
        meta = dict(artifact_version=1, model_version='METADATA-FIXTURE-NOT-A-MODEL',
            features=features or FEATURES, feature_schema_version=SCHEMA_VERSION, profile='tcp-observacao',
            window_seconds=10, versions=versions(), artifact_sha256=pin)
        (artifact.parent/'metadata.json').write_text(json.dumps(meta))
        return artifact.parent, pin, meta

    def test_ordered_float32_validation_and_metadata_fixture_not_called_a_model(self):
        result, _ = inspect_pcap(self.path, self.session, self.profile)
        directory, pin, _ = self.metadata(list(reversed(FEATURES)))
        compatibility = model_requirements(directory, pin, 'rf', result['windows'])
        self.assertEqual(compatibility['numeric_status'], 'COMPATIBLE')
        self.assertEqual(compatibility['ordered_columns'], list(reversed(FEATURES)))
        self.assertEqual(compatibility['dtype'], 'float32')
        self.assertFalse(compatibility['model_loaded'])

    def test_optional_missing_feature_profile_and_type_mismatch_are_reported(self):
        result, _ = inspect_pcap(self.path, self.session, self.profile)
        directory, pin, meta = self.metadata(FEATURES+['mqtt_publish_count'])
        check = model_requirements(directory, pin, 'rf', result['windows'])
        self.assertEqual(check['numeric_status'], 'INCOMPATIBLE')
        self.assertIn('mqtt_publish_count', next(iter(check['missing_by_window'].values())))
        meta['features'] = FEATURES; meta['profile'] = 'demo_tcp_ingress'
        (directory/'metadata.json').write_text(json.dumps(meta))
        self.assertEqual(model_requirements(directory,pin,'rf',result['windows'])['numeric_status'], 'INCOMPATIBLE')
        meta['profile']='tcp-observacao'; (directory/'metadata.json').write_text(json.dumps(meta))
        result['windows'][0]['packet_count'] = True
        self.assertEqual(model_requirements(directory,pin,'rf',result['windows'])['numeric_status'], 'INCOMPATIBLE')

    def test_no_pcap_or_model_does_not_gain_compatibility_or_coverage(self):
        result = audit(profile=self.profile, models={})
        self.assertEqual(result['models']['rf']['status'], 'NOT_VERIFIED')
        self.assertEqual(result['coverage']['status'], 'NOT_VERIFIED')
        self.assertFalse(result['authorized_for_inference'])
        self.assertFalse(result['inference_performed'])
        self.assertEqual(result['unmapped_optional_log_features'],
                         ['admin_auth_failures','connection_failures','mqtt_publish_count'])

    def test_unverified_session_and_duplicate_json_keys_rejected(self):
        with self.assertRaisesRegex(ValueError, 'session report'):
            audit(profile=self.profile, models={}, pcap=self.path)
        path = Path(self.temp.name)/'duplicate.json'
        path.write_text('{"features": [], "features": ["packet_count"]}')
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON key'):
            read_json(path)


if __name__ == '__main__':
    unittest.main()
