"""Transactional registry in the existing PostgreSQL, with no external effects.

One connection factory per caller; every mutation is a short transaction. Application
workers/verifiers are trusted backend integrations, never input from the browser.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from uuid import uuid4
import re

from psycopg import errors
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from harpisense_contracts.canonical import fingerprint
from harpisense_contracts.validation import timestamp

from .schema import (Capabilities, ConfigError, ID_PATTERN, REQUEST_SCHEMA,
                     checked, components_for, validate_document)


class Conflict(ConfigError):
    def __init__(self, code, current_revision=None):
        super().__init__(code)
        self.current_revision = current_revision


def migrate(connect):
    """Explicit invocation by installer; repeatable and checksummed, never startup."""
    sql = Path(__file__).with_name("001_config_manager.sql").read_text(encoding="utf-8")
    checksum = sha256(sql.encode()).hexdigest()
    with connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT pg_advisory_xact_lock(7261103101)")
        cur.execute("SELECT to_regclass('hs_config.migration') AS table_name")
        if cur.fetchone()["table_name"]:
            cur.execute("SELECT version, checksum FROM hs_config.migration")
            if cur.fetchall() != [{"version": 1, "checksum": checksum}]:
                raise ConfigError("MIGRATION_CHECKSUM_MISMATCH")
            return
        cur.execute(sql)
        cur.execute("INSERT INTO hs_config.migration VALUES (1, %s)", (checksum,))


def identifier(value):
    if type(value) is not str or not re.fullmatch(ID_PATTERN, value):
        raise ConfigError("INVALID_IDENTIFIER")
    return value


class ConfigStore:
    def __init__(self, connect, capabilities: Capabilities):
        self.connect = connect
        self.capabilities = capabilities

    @staticmethod
    def _audit(cur, op, actor, event, code="OK"):
        cur.execute("""INSERT INTO hs_config.audit
            (installation_id, operation_id, revision, actor, event, result_code)
            VALUES (%s,%s,%s,%s,%s,%s)""",
            (op["installation_id"], op["operation_id"], op["revision"],
             actor, event, code))

    @staticmethod
    def _head(cur, installation):
        cur.execute("SELECT * FROM hs_config.installation WHERE installation_id=%s FOR UPDATE",
                    (installation,))
        row = cur.fetchone()
        if row is None:
            raise ConfigError("INSTALLATION_NOT_FOUND")
        return row

    @staticmethod
    def _expected(head, expected):
        if type(expected) is not int or expected != head["desired_revision"]:
            raise Conflict("REVISION_CONFLICT", head["desired_revision"])

    @staticmethod
    def _operation(cur, operation_id):
        cur.execute("""SELECT o.*, r.document, r.fingerprint AS document_fingerprint
            FROM hs_config.operation o JOIN hs_config.revision r
            USING (installation_id, revision) WHERE operation_id=%s""", (operation_id,))
        row = cur.fetchone()
        if row is None:
            raise ConfigError("OPERATION_NOT_FOUND")
        return row

    def provision_registry(self, installation):
        """Register identity supplied by the installer, without inventing live values."""
        identifier(installation)
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO hs_config.installation (installation_id) VALUES (%s) ON CONFLICT DO NOTHING",
                        (installation,))

    def propose(self, installation, actor, request):
        identifier(installation)
        identifier(actor)  # Stable identity from authentication, not request JSON.
        req = checked(request, REQUEST_SCHEMA)
        document = validate_document(req["document"])
        digest = fingerprint(req)
        with self.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            head = self._head(cur, installation)
            cur.execute("""SELECT operation_id, request_fingerprint FROM hs_config.operation
                WHERE installation_id=%s AND actor=%s AND idempotency_key=%s""",
                (installation, actor, req["idempotency_key"]))
            previous = cur.fetchone()
            if previous:
                if previous["request_fingerprint"] != digest:
                    raise Conflict("IDEMPOTENCY_CONFLICT", head["desired_revision"])
                return self._operation(cur, previous["operation_id"])
            self._expected(head, req["expected_revision"])
            if head["active_operation"]:
                raise Conflict("APPLICATION_IN_PROGRESS", head["desired_revision"])
            revision = head["desired_revision"] + 1
            operation_id = uuid4()
            cur.execute("""INSERT INTO hs_config.revision
                (installation_id,revision,schema_version,document,fingerprint)
                VALUES (%s,%s,%s,%s,%s)""",
                (installation, revision, document["schema_version"], Jsonb(document), fingerprint(document)))
            try:
                cur.execute("""INSERT INTO hs_config.operation
                    (operation_id,installation_id,revision,actor,request_id,idempotency_key,
                     request_fingerprint,reason_code,status)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'DRAFT')""",
                    (operation_id, installation, revision, actor, req["request_id"],
                     req["idempotency_key"], digest, req["reason_code"]))
            except errors.UniqueViolation:
                raise Conflict("REQUEST_ID_CONFLICT", head["desired_revision"]) from None
            cur.execute("UPDATE hs_config.installation SET desired_revision=%s WHERE installation_id=%s",
                        (revision, installation))
            op = self._operation(cur, operation_id)
            self._audit(cur, op, actor, "PROPOSED")
            return op

    def validate(self, operation_id, actor, expected_revision):
        identifier(actor)
        failure = None
        with self.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            op = self._operation(cur, operation_id)
            head = self._head(cur, op["installation_id"])
            op = self._operation(cur, operation_id)
            self._expected(head, expected_revision)
            if op["revision"] != expected_revision:
                raise Conflict("SUPERSEDED_PROPOSAL", head["desired_revision"])
            if op["status"] == "VALIDATED" and op["capability_fingerprint"] == self.capabilities.digest:
                return op
            if op["status"] not in {"DRAFT", "VALIDATED"}:
                raise Conflict("INVALID_STATE", head["desired_revision"])
            try:
                self.capabilities.validate(op["document"])
            except ConfigError as exc:
                failure = str(exc)
            status = "REJECTED" if failure else "VALIDATED"
            cur.execute("""UPDATE hs_config.operation SET status=%s, capability_fingerprint=%s,
                updated_at=clock_timestamp() WHERE operation_id=%s""",
                (status, self.capabilities.digest, operation_id))
            self._audit(cur, op, actor, status, failure or "SCHEMA_AND_REFERENCES_ONLY")
            result = self._operation(cur, operation_id)
        if failure:
            raise ConfigError(failure)  # Rejection audit committed before returning error.
        return result

    def begin_application(self, operation_id, actor, expected_revision):
        """Persist intention before effects; returns fencing token and required plan.

        Does not reconnect MQTT, restart capture, resolve secrets or execute commands.
        """
        identifier(actor)
        with self.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            op = self._operation(cur, operation_id)
            head = self._head(cur, op["installation_id"])
            op = self._operation(cur, operation_id)
            self._expected(head, expected_revision)
            if op["revision"] != expected_revision:
                raise Conflict("SUPERSEDED_PROPOSAL", head["desired_revision"])
            if head["active_operation"] == op["operation_id"] and op["status"] == "APPLYING":
                return op
            if head["active_operation"] or op["status"] != "VALIDATED":
                raise Conflict("INVALID_STATE", head["desired_revision"])
            if op["capability_fingerprint"] != self.capabilities.digest:
                raise Conflict("CAPABILITIES_CHANGED", head["desired_revision"])
            self.capabilities.validate(op["document"])
            before = {}
            if head["effective_revision"]:
                cur.execute("SELECT document FROM hs_config.revision WHERE installation_id=%s AND revision=%s",
                            (op["installation_id"], head["effective_revision"]))
                before = cur.fetchone()["document"]
            components = components_for(before, op["document"])
            if not components:
                raise ConfigError("NO_EFFECTIVE_CHANGE")
            fence = head["fence"] + 1
            cur.execute("""UPDATE hs_config.installation SET active_operation=%s,fence=%s
                WHERE installation_id=%s""", (operation_id, fence, op["installation_id"]))
            cur.execute("""UPDATE hs_config.operation SET status='APPLYING',fence=%s,
                required_components=%s,updated_at=clock_timestamp() WHERE operation_id=%s""",
                (fence, Jsonb(components), operation_id))
            self._audit(cur, op, actor, "APPLYING")
            return self._operation(cur, operation_id)

    def record_verified(self, operation_id, fence, component, document_fingerprint,
                        verifier_ref, evidence_ref, observed_at):
        """Backend verifier boundary. Call only after actual observed-state check.

        This method MUST NOT be exposed as a browser endpoint or accept browser receipts.
        """
        for item in (component, verifier_ref, evidence_ref): identifier(item)
        if type(fence) is not int:
            raise ConfigError("INVALID_FENCE")
        try:
            observed = timestamp(observed_at)
        except ValueError:
            raise ConfigError("INVALID_OBSERVATION_TIME") from None
        with self.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            op = self._operation(cur, operation_id)
            head = self._head(cur, op["installation_id"])
            op = self._operation(cur, operation_id)
            self._active(head, op, fence)
            if component not in op["required_components"] or document_fingerprint != op["document_fingerprint"]:
                raise ConfigError("RECEIPT_SCOPE_MISMATCH")
            cur.execute("SELECT clock_timestamp() AS now")
            if observed < op["updated_at"] or observed > cur.fetchone()["now"]:
                raise ConfigError("STALE_OR_FUTURE_RECEIPT")
            cur.execute("SELECT * FROM hs_config.receipt WHERE operation_id=%s AND component=%s",
                        (operation_id, component))
            receipt = cur.fetchone()
            if receipt:
                if (receipt["fence"], receipt["document_fingerprint"], receipt["verifier_ref"],
                    receipt["evidence_ref"], receipt["observed_at"]) != (
                        fence, document_fingerprint, verifier_ref, evidence_ref, observed):
                    raise Conflict("RECEIPT_CONFLICT", head["desired_revision"])
                return
            cur.execute("""INSERT INTO hs_config.receipt
                (operation_id,component,fence,document_fingerprint,verifier_ref,evidence_ref,observed_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (operation_id, component, fence, document_fingerprint, verifier_ref, evidence_ref, observed))
            self._audit(cur, op, verifier_ref, "VERIFIED")

    @staticmethod
    def _active(head, op, fence):
        if (type(fence) is not int or head["active_operation"] != op["operation_id"]
                or head["fence"] != fence or op["fence"] != fence or op["status"] != "APPLYING"):
            raise Conflict("STALE_WORKER_OR_INVALID_STATE", head["desired_revision"])

    def confirm_application(self, operation_id, actor, fence):
        identifier(actor)
        with self.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            op = self._operation(cur, operation_id)
            head = self._head(cur, op["installation_id"])
            op = self._operation(cur, operation_id)
            if op["status"] == "APPLIED" and op["fence"] == fence:
                return op
            self._active(head, op, fence)
            cur.execute("SELECT component FROM hs_config.receipt WHERE operation_id=%s AND fence=%s",
                        (operation_id, fence))
            if {row["component"] for row in cur.fetchall()} != set(op["required_components"]):
                raise ConfigError("VERIFICATION_REQUIRED")
            cur.execute("""UPDATE hs_config.installation SET effective_revision=%s,active_operation=NULL
                WHERE installation_id=%s""", (op["revision"], op["installation_id"]))
            cur.execute("UPDATE hs_config.operation SET status='APPLIED',updated_at=clock_timestamp() WHERE operation_id=%s",
                        (operation_id,))
            self._audit(cur, op, actor, "APPLIED")
            return self._operation(cur, operation_id)

    def fail_application(self, operation_id, actor, fence, *, no_external_effects=False):
        """Unknown/partial effects retain the installation lock until reconciliation.

        FAILED may release it only when the trusted worker proved no external effects.
        No generic retry/rollback is provided in stage 1.
        """
        identifier(actor)
        if type(no_external_effects) is not bool:
            raise ConfigError("INVALID_FAILURE_RESULT")
        with self.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            op = self._operation(cur, operation_id)
            head = self._head(cur, op["installation_id"])
            op = self._operation(cur, operation_id)
            self._active(head, op, fence)
            cur.execute("SELECT 1 FROM hs_config.receipt WHERE operation_id=%s LIMIT 1", (operation_id,))
            if no_external_effects and cur.fetchone():
                raise ConfigError("EXTERNAL_EFFECTS_ALREADY_VERIFIED")
            status = "FAILED" if no_external_effects else "RECOVERY_REQUIRED"
            cur.execute("UPDATE hs_config.operation SET status=%s,updated_at=clock_timestamp() WHERE operation_id=%s",
                        (status, operation_id))
            # Invalidate old workers, including those holding the previous valid token.
            cur.execute("""UPDATE hs_config.installation SET fence=fence+1,
                active_operation=CASE WHEN %s THEN NULL ELSE active_operation END WHERE installation_id=%s""",
                (no_external_effects, op["installation_id"]))
            self._audit(cur, op, actor, status)

    def current(self, installation):
        identifier(installation)
        with self.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            # Single statement gives one consistent desired/effective snapshot.
            cur.execute("""SELECT i.*, d.document AS proposed, d.fingerprint AS proposed_fingerprint,
                o.status AS proposed_status, e.document AS effective
                FROM hs_config.installation i
                LEFT JOIN hs_config.revision d ON (d.installation_id=i.installation_id AND d.revision=i.desired_revision)
                LEFT JOIN hs_config.operation o ON (o.installation_id=i.installation_id AND o.revision=i.desired_revision)
                LEFT JOIN hs_config.revision e ON (e.installation_id=i.installation_id AND e.revision=i.effective_revision)
                WHERE i.installation_id=%s""", (installation,))
            result = cur.fetchone()
            if result is None: raise ConfigError("INSTALLATION_NOT_FOUND")
            return result

    def history(self, installation, *, after=0, limit=100):
        identifier(installation)
        if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 500:
            raise ConfigError("INVALID_PAGE")
        with self.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM hs_config.audit WHERE installation_id=%s AND id>%s ORDER BY id LIMIT %s",
                        (installation, after, limit))
            return cur.fetchall()

    def revision(self, installation, revision):
        """Historical immutable document plus its own operation/validation state."""
        identifier(installation)
        if type(revision) is not int or revision < 1:
            raise ConfigError("INVALID_REVISION")
        with self.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""SELECT r.*,o.operation_id,o.status,o.capability_fingerprint,
                o.required_components FROM hs_config.revision r JOIN hs_config.operation o
                USING (installation_id,revision) WHERE installation_id=%s AND revision=%s""",
                (installation, revision))
            result = cur.fetchone()
            if result is None: raise ConfigError("REVISION_NOT_FOUND")
            return result

    def pending_reconciliation(self, installation):
        """After restart: inspect and reconcile; never replay an external command."""
        identifier(installation)
        with self.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""SELECT operation_id,revision,status,fence,required_components FROM hs_config.operation
                WHERE installation_id=%s AND status IN ('APPLYING','RECOVERY_REQUIRED') ORDER BY revision""",
                (installation,))
            return cur.fetchall()
