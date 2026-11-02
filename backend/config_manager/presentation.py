"""Limited real applicator and application consumer. No OS timezone mutation.

The installer supplies a private persistent directory. Atomic files carry only
presentation values and a recovery journal. PostgreSQL remains the sole registry.
All supported writers/recovery use one session advisory lock per installation.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from psycopg.rows import dict_row
from harpisense_contracts.canonical import fingerprint
from .schema import ConfigError, validate_document
from .store import Conflict


def parameters(value):
    doc = validate_document({'schema_version': '1.0.0', 'record_type': 'config.document',
                             'parameters': value})
    p = doc['parameters']
    if set(p) != {'display_name', 'timezone'} or not p['display_name'].strip():
        raise ConfigError('PRESENTATION_SCOPE_ONLY')
    return p


class PresentationConsumer:
    """The backend's actual display metadata/time formatter, independent of proposal."""
    def __init__(self, directory, installation):
        self.directory = Path(directory).resolve()
        self.installation = installation
        self.path = self.directory / 'presentation.json'

    def read(self):
        if not self.path.exists():
            return {'installation_id': self.installation, 'revision': None,
                    'parameters': {'display_name': 'HarpiSense', 'timezone': 'UTC'},
                    'document_fingerprint': None, 'fence': 0}
        value = json.loads(self.path.read_text(encoding='utf-8'))
        if value['installation_id'] != self.installation:
            raise ConfigError('PRESENTATION_IDENTITY_MISMATCH')
        parameters(value['parameters'])
        return value

    def observe(self, instant='2026-11-01T12:00:00Z'):
        value = self.read()
        # Preserve the original instant, exposing a separately formatted view.
        date = datetime.fromisoformat(instant.replace('Z', '+00:00'))
        if date.tzinfo is None:
            raise ConfigError('PRESENTATION_INSTANT_REQUIRES_OFFSET')
        return {**value, 'original_instant': instant,
                'displayed_instant': date.astimezone(ZoneInfo(value['parameters']['timezone'])).isoformat()}


class PresentationApplicator:
    def __init__(self, store, installation, directory, *, fault=None):
        self.store, self.installation = store, installation
        self.consumer = PresentationConsumer(directory, installation)
        self.directory = self.consumer.directory
        self.journal_path = self.directory / 'presentation-journal.json'
        self.fault = fault or (lambda stage: None)  # Trusted test injection only.

    def _write(self, path, value):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
        try:
            with temporary.open('x', encoding='utf-8', newline='\n') as stream:
                os.chmod(temporary, 0o600)
                json.dump(value, stream, sort_keys=True, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    @contextmanager
    def _lock(self):
        with self.store.connect() as conn:
            conn.autocommit = True
            key = 'presentation:' + self.installation
            if not conn.execute('SELECT pg_try_advisory_lock(hashtextextended(%s,0))', (key,)).fetchone()[0]:
                raise Conflict('APPLICATION_IN_PROGRESS')
            try:
                yield
            finally:
                conn.execute('SELECT pg_advisory_unlock(hashtextextended(%s,0))', (key,))

    def _guarded_write(self, plan, value, *, recovery=False):
        with self.store.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            head = self.store._head(cur, self.installation)
            op = self.store._operation(cur, UUID(str(plan['operation_id'])))
            if recovery:
                if (str(head['active_operation']) != str(plan['operation_id'])
                        or head['fence'] != plan['recovery_fence']
                        or op['status'] not in {'APPLYING', 'RECOVERY_REQUIRED'}):
                    raise Conflict('STALE_RECOVERY')
            else:
                self.store._active(head, op, plan['fence'])
            # No newer registry worker can invalidate the fence mid-write.
            self._write(self.consumer.path, value)

    def _verify(self, value):
        observed = self.consumer.observe()
        if any(observed[k] != value[k] for k in value):
            raise ConfigError('PRESENTATION_READBACK_MISMATCH')
        expected = datetime(2026, 11, 1, 12, tzinfo=timezone.utc).astimezone(
            ZoneInfo(value['parameters']['timezone'])).isoformat()
        if observed['displayed_instant'] != expected:
            raise ConfigError('PRESENTATION_FORMAT_MISMATCH')
        return observed

    def _journal(self):
        return json.loads(self.journal_path.read_text(encoding='utf-8')) if self.journal_path.exists() else None

    def _recover_locked(self, journal):
        operation_id = UUID(journal['operation_id'])
        current = self.store.current(self.installation)
        op = self.store.revision(self.installation, journal['revision'])
        expected_target = {'installation_id': self.installation, 'revision': op['revision'],
                           'fence': op['fence'], 'document_fingerprint': fingerprint(op['document']),
                           'parameters': parameters(op['document']['parameters'])}
        if str(op['operation_id']) != str(operation_id) or journal['target'] != expected_target:
            raise ConfigError('PRESENTATION_JOURNAL_MISMATCH')
        if op['status'] == 'APPLIED':
            self._verify(journal['target'])
            journal['phase'] = 'applied'
            self._write(self.journal_path, journal)
            return
        previous = journal['before']
        expected_parameters = (current['effective']['parameters'] if current['effective'] else
                               {'display_name': 'HarpiSense', 'timezone': 'UTC'})
        expected_fingerprint = fingerprint(current['effective']) if current['effective'] else None
        if (previous['installation_id'] != self.installation
                or previous['revision'] != current['effective_revision']
                or previous['parameters'] != expected_parameters
                or previous['document_fingerprint'] != expected_fingerprint):
            raise ConfigError('PRESENTATION_PREVIOUS_SNAPSHOT_MISMATCH')
        if op['status'] == 'FAILED':
            self._verify(journal['before'])
            journal['phase'] = 'rolled_back'
            self._write(self.journal_path, journal)
            return
        journal['recovery_fence'] = current['fence']
        self.fault('rollback_write')
        self._guarded_write(journal, journal['before'], recovery=True)
        self.fault('rollback_verify')
        self._verify(journal['before'])
        self.store.finish_recovery(operation_id, 'presentation-worker', journal['recovery_fence'])
        journal['phase'] = 'rolled_back'
        self._write(self.journal_path, journal)

    def recover(self):
        """Restore a durable prior snapshot after interruption, never replay target."""
        with self._lock():
            journal = self._journal()
            if journal and journal['phase'] not in {'applied', 'rolled_back'}:
                self._recover_locked(journal)

    def observe(self):
        try:
            observed = self.consumer.observe()
            head = self.store.current(self.installation)
            journal = self._journal()
            verified = (not head['active_operation'] and
                        (not journal or journal['phase'] in {'applied', 'rolled_back'}) and
                        observed['revision'] == head['effective_revision'] and
                        (head['effective'] is None or
                         (observed['parameters'] == head['effective']['parameters'] and
                          observed['document_fingerprint'] == fingerprint(head['effective']))))
            return {**observed, 'verified': bool(verified),
                    'status': ('verified' if observed['revision'] is not None else 'bootstrap_defaults') if verified else 'unknown',
                    'last_result': journal['phase'] if journal else None,
                    'operational': False}
        except Exception:
            return {'status': 'unknown', 'verified': False, 'operational': False}

    def apply(self, operation_id, expected_revision):
        with self._lock():
            current = self.store.current(self.installation)
            op = self.store.revision(self.installation, expected_revision)
            if str(op['operation_id']) != str(operation_id):
                raise Conflict('SUPERSEDED_PROPOSAL', current['desired_revision'])
            self.store._expected(current, expected_revision)
            p = parameters(op['document']['parameters'])
            # Refuse removals/changes to any previously effective unsupported group.
            if current['effective'] and set(current['effective']['parameters']) - {'display_name', 'timezone'}:
                raise ConfigError('PRESENTATION_SCOPE_ONLY')
            if op['status'] == 'APPLIED':
                observed = self.observe()
                if not observed['verified']:
                    raise ConfigError('PRESENTATION_STATE_UNKNOWN')
                return {'status': 'APPLIED', 'idempotent': True, 'presentation': observed, 'operational': False}
            if op['status'] == 'FAILED':
                return {'status': 'FAILED', 'idempotent': True,
                        'presentation': self.observe(), 'operational': False}
            if self.observe()['status'] == 'unknown':
                raise Conflict('PRESENTATION_RECOVERY_REQUIRED', current['desired_revision'])
            before = self.consumer.read()
            plan = self.store.begin_application(operation_id, 'admin-account-1', expected_revision)
            journal = {'operation_id': str(operation_id), 'revision': expected_revision,
                       'fence': plan['fence'], 'phase': 'pending', 'before': before,
                       'target': {'installation_id': self.installation, 'revision': expected_revision,
                                  'fence': plan['fence'], 'document_fingerprint': plan['document_fingerprint'],
                                  'parameters': p}}
            try:
                self._write(self.journal_path, journal)  # Durable before side effects.
                self.fault('before_write')
                self._guarded_write(plan, journal['target'])
                self.fault('after_write')
                self._verify(journal['target'])
                self.fault('after_verify')
                self.store.record_verified(operation_id, plan['fence'], 'config-registry',
                    plan['document_fingerprint'], 'presentation-consumer',
                    'presentation-' + str(operation_id), datetime.now(timezone.utc).isoformat())
                self.store.confirm_application(operation_id, 'presentation-worker', plan['fence'])
                journal['phase'] = 'applied'
                self._write(self.journal_path, journal)
                return {'status': 'APPLIED', 'idempotent': False, 'presentation': self.observe(), 'operational': False}
            except Exception:
                # If confirmation committed, never restore over the effective target.
                try:
                    self._recover_locked(journal)
                except Exception:
                    try:
                        head = self.store.current(self.installation)
                        if head['active_operation']:
                            self.store.fail_application(operation_id, 'presentation-worker', plan['fence'])
                    except Exception:
                        pass  # Durable pending journal + active op still block effects.
                    return {'status': 'RECOVERY_REQUIRED', 'presentation': self.observe(), 'operational': False}
                return {'status': 'APPLIED' if journal['phase'] == 'applied' else 'FAILED',
                        'recovery': journal['phase'], 'presentation': self.observe(), 'operational': False}
