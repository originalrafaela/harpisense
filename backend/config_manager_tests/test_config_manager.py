"""Real PostgreSQL acceptance tests. Synthetic state; no operational applicators."""
import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import threading
import unittest
from uuid import uuid4

import psycopg
from jsonschema import Draft202012Validator

from config_manager.schema import (Capabilities, ConfigError, DOCUMENT_SCHEMA,
                                   REQUEST_SCHEMA, validate_document)
from config_manager.store import ConfigStore, Conflict, migrate


def document(**parameters):
    return {"schema_version": "1.0.0", "record_type": "config.document", "parameters": parameters}


def request(revision=0, doc=None):
    return {"schema_version": "1.0.0", "record_type": "config.proposal",
            "request_id": str(uuid4()), "idempotency_key": str(uuid4()),
            "expected_revision": revision, "reason_code": "ADMIN_CHANGE",
            "document": doc or document(display_name="Synthetic installation")}


CAPABILITIES = Capabilities(
    revision="synthetic-1", secret_refs=frozenset({"secret://mqtt/consumer-1"}),
    ca_refs=frozenset({"test-ca"}), mqtt_hosts=frozenset({"broker.invalid"}),
    mqtt_topics=frozenset({"harpisense/v1/telemetry/poste2"}),
    network_cidrs=frozenset({"192.0.2.0/24"}),
    sensors=frozenset({("sensor-1", "gateway-1")}),
    capture_profiles=frozenset({"mqtt-approved"}),
    rf_models=frozenset({("rf-approved-1", "harpisense.if.window.v1")}),
    protocol_adapters=frozenset({"mqtt-v1"}),
)


def mqtt_document():
    return document(mqtt_broker_host="broker.invalid", mqtt_broker_port=8883,
                    mqtt_tls_mode="required", mqtt_ca_ref="test-ca",
                    mqtt_identity_secret_ref="secret://mqtt/consumer-1",
                    mqtt_topics=["harpisense/v1/telemetry/poste2"], mqtt_client_id="test-consumer")


class SchemaTests(unittest.TestCase):
    def test_schemas_are_valid_and_export_matches(self):
        for name, schema in (("document", DOCUMENT_SCHEMA), ("proposal", REQUEST_SCHEMA)):
            Draft202012Validator.check_schema(schema)
            exported = json.loads((Path(__file__).parents[1] / "config_manager" / "schemas" /
                                   f"config.{name}.v1.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(exported, schema)

    def test_types_versions_limits_and_reserved_authorities(self):
        invalid = [document(mqtt_broker_port=True), document(mqtt_broker_port=65536),
                   document(capture_window_seconds=2), document(display_name="x" * 101),
                   document(timezone="No/SuchZone"), document(display_name="bad\nname"),
                   document(api_bind="0.0.0.0:8000"), document(postgres_dsn_ref="secret://db/main"),
                   document(autonomy_mode=3), document(operation_mode="REAL"),
                   document(execution_enabled=True), document(admin_auth_policy={}),
                   document(firewall_command="nft flush ruleset"), document(other=float("nan"))]
        bad_version = document(display_name="test")
        bad_version["schema_version"] = "2.0.0"
        invalid.append(bad_version)
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ConfigError):
                validate_document(value)

    def test_secret_values_unknown_keys_and_embedded_credentials_rejected_without_echo(self):
        secret = "sensitive-value-never-echo"
        for value in [document(password=secret), document(mqtt_identity_secret_ref=secret),
                      document(external_credential_ref="https://user:" + secret + "@host"),
                      document(vpn_auth_ref="secret://vpn/token?value=" + secret),
                      document(**{secret: secret})]:
            with self.subTest(value=value):
                try:
                    validate_document(value)
                except ConfigError as exc:
                    self.assertNotIn(secret, str(exc))
                else:
                    self.fail("Secret document accepted")
        value = mqtt_document()
        value["parameters"]["mqtt_broker_host"] = "user:" + secret + "@broker.invalid"
        with self.assertRaises(ConfigError) as raised:
            validate_document(value)
        self.assertNotIn(secret, str(raised.exception))

    def test_networks_require_unambiguous_bindings_and_do_not_set_visibility(self):
        valid = document(network_cidrs=["192.0.2.0/24"], sensor_bindings=[{
            "sensor_id": "sensor-1", "network": "192.0.2.0/24", "observation_point": "gateway-1"}])
        CAPABILITIES.validate(valid)
        self.assertNotIn("monitored", json.dumps(valid))
        for mutate in [lambda p: p.pop("sensor_bindings"),
                       lambda p: p["network_cidrs"].append("192.0.2.0/25"),
                       lambda p: p["sensor_bindings"][0].update(status="MONITORED"),
                       lambda p: p["sensor_bindings"][0].update(observation_point="unknown"),
                       lambda p: (p.update(network_cidrs=["198.51.100.0/24"]),
                                  p["sensor_bindings"][0].update(network="198.51.100.0/24")),
                       lambda p: p["sensor_bindings"].append(dict(p["sensor_bindings"][0]))]:
            changed = copy.deepcopy(valid)
            mutate(changed["parameters"])
            with self.assertRaises(ConfigError): CAPABILITIES.validate(changed)

    def test_catalog_acl_model_and_secret_references_fail_closed(self):
        CAPABILITIES.validate(mqtt_document())
        for field, value in [("mqtt_identity_secret_ref", "secret://mqtt/missing"),
                             ("mqtt_broker_host", "other.invalid"),
                             ("mqtt_ca_ref", "missing"), ("mqtt_tls_mode", "disabled"),
                             ("mqtt_topics", ["harpisense/#"])]:
            changed = mqtt_document()
            changed["parameters"][field] = value
            with self.assertRaises(ConfigError): CAPABILITIES.validate(changed)
        CAPABILITIES.validate(document(rf_model_ref="rf-approved-1", feature_schema_version="harpisense.if.window.v1"))
        with self.assertRaises(ConfigError):
            CAPABILITIES.validate(document(rf_model_ref="unapproved", feature_schema_version="harpisense.if.window.v1"))


@unittest.skipUnless(os.environ.get("HARPISENSE_CONFIG_TEST_DSN"), "isolated PostgreSQL DSN required")
class PostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["HARPISENSE_CONFIG_TEST_DSN"]
        cls.connect = staticmethod(lambda: psycopg.connect(cls.dsn))
        # Hard guard: never run acceptance tests against an operational database.
        with cls.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            if cur.fetchone()[0] != "config_fixture":
                raise RuntimeError("Tests require database config_fixture")
            cur.execute("CREATE TABLE IF NOT EXISTS public.config_test_sentinel (id integer PRIMARY KEY)")
            cur.execute("INSERT INTO public.config_test_sentinel VALUES (1) ON CONFLICT DO NOTHING")
        migrate(cls.connect)

    def setUp(self):
        self.store = ConfigStore(self.connect, CAPABILITIES)
        self.installation = "test-" + uuid4().hex
        self.store.provision_registry(self.installation)

    def propose(self, doc=None, revision=0):
        return self.store.propose(self.installation, "admin-1", request(revision, doc))

    def ready(self, doc=None, revision=0):
        op = self.propose(doc, revision)
        return self.store.validate(op["operation_id"], "admin-1", op["revision"])

    def apply(self, op):
        active = self.store.begin_application(op["operation_id"], "admin-1", op["revision"])
        for component in active["required_components"]:
            self.receipt(active, component)
        return self.store.confirm_application(active["operation_id"], "admin-1", active["fence"])

    def receipt(self, op, component, **overrides):
        args = dict(operation_id=op["operation_id"], fence=op["fence"], component=component,
                    document_fingerprint=op["document_fingerprint"], verifier_ref="synthetic-verifier",
                    evidence_ref="synthetic-receipt-1", observed_at=datetime.now(timezone.utc).isoformat())
        args.update(overrides)
        self.store.record_verified(**args)
        return args

    def test_migration_repeatable_and_preserves_unrelated_tables(self):
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS public.config_test_sentinel (id integer PRIMARY KEY)")
            cur.execute("INSERT INTO public.config_test_sentinel VALUES (1) ON CONFLICT DO NOTHING")
        migrate(self.connect)
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT id FROM public.config_test_sentinel")
            self.assertEqual(cur.fetchall(), [(1,)])
            cur.execute("SELECT count(*) FROM hs_config.migration")
            self.assertEqual(cur.fetchone()[0], 1)

    def test_empty_registry_does_not_invent_laboratory_state(self):
        current = self.store.current(self.installation)
        self.assertEqual(current["desired_revision"], 0)
        self.assertIsNone(current["effective_revision"])
        self.assertIsNone(current["effective"])

    def test_draft_validated_and_effective_are_distinct(self):
        op = self.propose()
        current = self.store.current(self.installation)
        self.assertEqual(current["proposed_status"], "DRAFT")
        self.assertIsNone(current["effective_revision"])
        validated = self.store.validate(op["operation_id"], "admin-1", 1)
        self.assertEqual(validated["status"], "VALIDATED")
        self.assertIsNone(self.store.current(self.installation)["effective_revision"])
        active = self.store.begin_application(op["operation_id"], "admin-1", 1)
        with self.assertRaisesRegex(ConfigError, "VERIFICATION_REQUIRED"):
            self.store.confirm_application(op["operation_id"], "admin-1", active["fence"])
        self.receipt(active, "config-registry")
        self.store.confirm_application(op["operation_id"], "admin-1", active["fence"])
        current = self.store.current(self.installation)
        self.assertEqual(current["effective_revision"], 1)
        self.assertEqual(current["effective"], op["document"])
        self.assertEqual([e["event"] for e in self.store.history(self.installation)],
                         ["PROPOSED", "VALIDATED", "APPLYING", "VERIFIED", "APPLIED"])

    def test_idempotency_persists_across_store_recreation_and_conflicting_reuse(self):
        req = request()
        one = self.store.propose(self.installation, "admin-1", req)
        recreated = ConfigStore(self.connect, CAPABILITIES)
        two = recreated.propose(self.installation, "admin-1", req)
        self.assertEqual(one["operation_id"], two["operation_id"])
        self.assertEqual(len(self.store.history(self.installation)), 1)
        changed = copy.deepcopy(req)
        changed["document"] = document(display_name="different")
        with self.assertRaisesRegex(Conflict, "IDEMPOTENCY_CONFLICT"):
            recreated.propose(self.installation, "admin-1", changed)
        changed = copy.deepcopy(req)
        changed.update(idempotency_key=str(uuid4()), expected_revision=1)
        with self.assertRaisesRegex(Conflict, "REQUEST_ID_CONFLICT"):
            recreated.propose(self.installation, "admin-1", changed)
        self.assertEqual(self.store.current(self.installation)["desired_revision"], 1)

    def test_simultaneous_writers_have_one_winner_and_one_conflict(self):
        barrier = threading.Barrier(2)
        def writer(index):
            barrier.wait()
            try:
                return self.store.propose(self.installation, "admin-1", request(doc=document(display_name=f"Writer {index}")))
            except Conflict as exc:
                return exc
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(writer, range(2)))
        self.assertEqual(sum(isinstance(r, Conflict) for r in results), 1)
        error = next(r for r in results if isinstance(r, Conflict))
        self.assertEqual(error.current_revision, 1)
        self.assertEqual(len(self.store.history(self.installation)), 1)

    def test_simultaneous_identical_retry_creates_one_operation(self):
        req = request()
        barrier = threading.Barrier(2)
        def writer(_):
            barrier.wait()
            return self.store.propose(self.installation, "admin-1", req)["operation_id"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(writer, range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(self.store.history(self.installation)), 1)

    def test_superseded_proposal_and_capability_changes_cannot_apply(self):
        op = self.ready()
        other = ConfigStore(self.connect, Capabilities(revision="different"))
        with self.assertRaisesRegex(Conflict, "CAPABILITIES_CHANGED"):
            other.begin_application(op["operation_id"], "admin-1", 1)
        self.propose(document(display_name="new"), 1)
        with self.assertRaisesRegex(Conflict, "REVISION_CONFLICT"):
            self.store.begin_application(op["operation_id"], "admin-1", 1)
        with self.assertRaisesRegex(Conflict, "SUPERSEDED_PROPOSAL"):
            self.store.begin_application(op["operation_id"], "admin-1", 2)

    def test_reference_rejection_is_durable_and_does_not_change_effective(self):
        self.apply(self.ready())
        bad = self.propose(document(external_credential_ref="secret://cloud/missing"), 1)
        with self.assertRaisesRegex(ConfigError, "UNKNOWN_SECRET_REFERENCE"):
            self.store.validate(bad["operation_id"], "admin-1", 2)
        current = self.store.current(self.installation)
        self.assertEqual(current["proposed_status"], "REJECTED")
        self.assertEqual(current["effective_revision"], 1)
        self.assertEqual(self.store.history(self.installation)[-1]["event"], "REJECTED")

    def test_partial_failure_restart_and_fencing_preserve_effective_state(self):
        self.apply(self.ready())
        op = self.ready(mqtt_document(), 1)
        active = self.store.begin_application(op["operation_id"], "admin-1", 2)
        restarted = ConfigStore(self.connect, CAPABILITIES)
        self.assertEqual(restarted.pending_reconciliation(self.installation)[0]["status"], "APPLYING")
        self.receipt(active, "mqtt")
        with self.assertRaisesRegex(ConfigError, "VERIFICATION_REQUIRED"):
            self.store.confirm_application(op["operation_id"], "admin-1", active["fence"])
        restarted.fail_application(op["operation_id"], "worker-1", active["fence"])
        self.assertEqual(restarted.pending_reconciliation(self.installation)[0]["status"], "RECOVERY_REQUIRED")
        self.assertEqual(restarted.current(self.installation)["effective_revision"], 1)
        with self.assertRaisesRegex(Conflict, "STALE_WORKER"):
            self.receipt(active, "config-registry")
        with self.assertRaisesRegex(Conflict, "APPLICATION_IN_PROGRESS"):
            self.propose(document(display_name="unsafe retry"), 2)

    def test_no_effect_failure_unlocks_and_old_worker_cannot_confirm_new_operation(self):
        op = self.ready()
        active = self.store.begin_application(op["operation_id"], "admin-1", 1)
        self.store.fail_application(op["operation_id"], "worker-1", active["fence"], no_external_effects=True)
        next_op = self.ready(document(display_name="next"), 1)
        next_active = self.store.begin_application(next_op["operation_id"], "admin-1", 2)
        self.assertGreater(next_active["fence"], active["fence"])
        with self.assertRaises(Conflict):
            self.store.confirm_application(op["operation_id"], "admin-1", active["fence"])

    def test_receipt_scope_freshness_idempotency_and_conflicting_overwrite(self):
        op = self.ready()
        active = self.store.begin_application(op["operation_id"], "admin-1", 1)
        for overrides in [dict(fence=active["fence"] + 1), dict(document_fingerprint="0" * 64),
                          dict(observed_at="2020-01-01T00:00:00Z"),
                          dict(observed_at=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat())]:
            with self.assertRaises(ConfigError): self.receipt(active, "config-registry", **overrides)
        with self.assertRaises(ConfigError): self.receipt(active, "unrelated")
        args = self.receipt(active, "config-registry")
        self.store.record_verified(**args)
        args["evidence_ref"] = "different-receipt"
        with self.assertRaisesRegex(Conflict, "RECEIPT_CONFLICT"):
            self.store.record_verified(**args)
        with self.assertRaisesRegex(ConfigError, "EXTERNAL_EFFECTS_ALREADY_VERIFIED"):
            self.store.fail_application(op["operation_id"], "worker-1", active["fence"], no_external_effects=True)

    def test_immutable_documents_audit_receipts_and_no_secret_in_database(self):
        op = self.ready(mqtt_document())
        self.apply(op)
        for table in ("revision", "audit", "receipt"):
            with self.assertRaises(psycopg.IntegrityError):
                with self.connect() as conn, conn.cursor() as cur:
                    # Identifiers are fixed local constants, never user values.
                    cur.execute(f"DELETE FROM hs_config.{table}")
        secret = "sensitive-value-never-persist"
        with self.assertRaises(ConfigError):
            self.propose(document(mqtt_password=secret), 1)
        with self.connect() as conn, conn.cursor() as cur:
            for table in ("revision", "operation", "audit", "receipt"):
                cur.execute(f"SELECT row_to_json(t)::text FROM hs_config.{table} t")
                self.assertNotIn(secret, str(cur.fetchall()))
        self.assertIn("secret://mqtt/consumer-1", json.dumps(self.store.current(self.installation), default=str))

    def test_audit_pagination_and_isolation(self):
        self.ready()
        first = self.store.history(self.installation, limit=1)
        next_page = self.store.history(self.installation, after=first[0]["id"])
        self.assertEqual([x["event"] for x in next_page], ["VALIDATED"])
        self.assertEqual(self.store.history("another-installation"), [])
        with self.assertRaises(ConfigError): self.store.history(self.installation, limit=501)

    def test_historical_revision_remains_readable_after_new_proposal(self):
        first = self.ready()
        self.propose(document(display_name="new proposal"), 1)
        saved = self.store.revision(self.installation, 1)
        self.assertEqual(saved["document"], first["document"])
        self.assertEqual(saved["status"], "VALIDATED")
        with self.assertRaises(ConfigError): self.store.revision("other-installation", 1)
        with self.assertRaises(ConfigError): self.store.revision(self.installation, True)

    def test_multiple_services_need_all_matching_receipts_before_effective_changes(self):
        mixed = mqtt_document()
        mixed["parameters"]["display_name"] = "Mixed synthetic config"
        op = self.ready(mixed)
        active = self.store.begin_application(op["operation_id"], "admin-1", 1)
        self.assertEqual(active["required_components"], ["config-registry", "mqtt"])
        self.receipt(active, "config-registry")
        with self.assertRaisesRegex(ConfigError, "VERIFICATION_REQUIRED"):
            self.store.confirm_application(op["operation_id"], "admin-1", active["fence"])
        self.assertIsNone(self.store.current(self.installation)["effective"])
        self.receipt(active, "mqtt")
        self.store.confirm_application(op["operation_id"], "admin-1", active["fence"])
        self.assertEqual(self.store.current(self.installation)["effective"], mixed)

    def test_runtime_role_can_use_registry_but_cannot_truncate_or_mutate_history(self):
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute("""DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='config_fixture_runtime') THEN
                    CREATE ROLE config_fixture_runtime NOLOGIN;
                END IF;
                END $$""")
            cur.execute("GRANT USAGE ON SCHEMA hs_config TO config_fixture_runtime")
            cur.execute("GRANT SELECT,INSERT,UPDATE ON hs_config.installation,hs_config.operation TO config_fixture_runtime")
            cur.execute("GRANT SELECT,INSERT ON hs_config.revision,hs_config.audit,hs_config.receipt TO config_fixture_runtime")
            cur.execute("GRANT USAGE ON SEQUENCE hs_config.audit_id_seq TO config_fixture_runtime")
        def runtime_connect():
            conn = self.connect()
            conn.execute("SET ROLE config_fixture_runtime")
            return conn
        runtime = ConfigStore(runtime_connect, CAPABILITIES)
        op = runtime.propose(self.installation, "admin-1", request())
        runtime.validate(op["operation_id"], "admin-1", 1)
        active = runtime.begin_application(op["operation_id"], "admin-1", 1)
        runtime.record_verified(active["operation_id"], active["fence"], "config-registry",
                                active["document_fingerprint"], "synthetic-verifier",
                                "runtime-receipt-1", datetime.now(timezone.utc).isoformat())
        runtime.confirm_application(active["operation_id"], "admin-1", active["fence"])
        for query in ("TRUNCATE hs_config.audit", "DELETE FROM hs_config.revision",
                      "UPDATE hs_config.audit SET event='APPLIED'"):
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with runtime_connect() as conn:
                    conn.execute(query)
        self.assertEqual(len(runtime.history(self.installation)), 5)


if __name__ == "__main__":
    unittest.main()
