"""PostgreSQL only. Cross-process lock, settings and audit share one transaction."""
from contextlib import contextmanager
import psycopg
from psycopg.types.json import Jsonb
from .controls import LOCK_ID


class Transaction:
    def __init__(self, conn):
        self.conn = conn

    def read(self):
        row = self.conn.execute('SELECT value,revision,emergency_stopped,updated_at FROM hs_control WHERE id=1').fetchone()
        if row is None:
            raise RuntimeError('Control migration required')
        return dict(value=row[0], revision=row[1], emergency_stopped=row[2], updated_at=row[3].isoformat())

    def save(self, value, revision, stopped):
        self.conn.execute('UPDATE hs_control SET value=%s,revision=%s,emergency_stopped=%s,updated_at=clock_timestamp() WHERE id=1',
                          (Jsonb(value), revision, stopped))

    def log(self, actor, operation, details):
        self.conn.execute('INSERT INTO hs_control_audit(actor,operation,details) VALUES(%s,%s,%s)',
                          (actor, operation, Jsonb(details)))

    def simulation_once(self, decision_id, result):
        row = self.conn.execute('SELECT result FROM hs_simulation WHERE decision_id=%s', (decision_id,)).fetchone()
        if row:
            return row[0]
        self.conn.execute('INSERT INTO hs_simulation(decision_id,result) VALUES(%s,%s)', (decision_id, Jsonb(result)))
        self.log('isolated-simulator', 'SIMULATED', result)
        return result


class PostgresControls:
    def __init__(self, conninfo):
        self.conninfo = conninfo

    @contextmanager
    def transaction(self):
        with psycopg.connect(self.conninfo, connect_timeout=5) as conn:
            # Default READ COMMITTED: waiter sees the committed winner after lock acquisition.
            conn.execute('SET TRANSACTION ISOLATION LEVEL READ COMMITTED')
            conn.execute("SET LOCAL lock_timeout='5s'")
            conn.execute('SELECT pg_advisory_xact_lock(%s)', (LOCK_ID,))
            yield Transaction(conn)

    def audit(self, limit=50, offset=0):
        with psycopg.connect(self.conninfo, connect_timeout=5) as conn:
            rows = conn.execute('SELECT id,actor,operation,details,at FROM hs_control_audit ORDER BY id DESC LIMIT %s OFFSET %s',
                                (limit, offset)).fetchall()
        return [dict(id=str(r[0]), revision=1, source='control-service', created_at=r[4].isoformat(),
                     data=dict(actor=r[1], operation=r[2], details=r[3], observed_at=r[4].isoformat())) for r in rows]
