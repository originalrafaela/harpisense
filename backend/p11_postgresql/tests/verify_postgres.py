"""Integration and volume comparison; refuses any database except the test container."""
import hashlib
import json
import platform
import subprocess
import sys
import time
import tracemalloc
import unittest
from pathlib import Path
from types import SimpleNamespace
from importlib.metadata import version

import psycopg
from psycopg.types.json import Jsonb
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(Path(__file__).parent / 'fixtures')]
from postgres_store import PostgresStore
from previous_store import PostgresStore as PreviousStore
from backend11.service import create_app
from harpia_deterministic.p11 import install_deterministic_harpia, explain

DSN = 'host=p11-pagination-tests dbname=p11_pagination_test user=p11_test'
REPORT = {'synthetic_only': True, 'database': 'p11_pagination_test', 'container': 'p11-pagination-tests'}
REPORT['client_environment'] = dict(python=sys.version, platform=platform.platform(),
    dependencies={name: version(name) for name in ('psycopg', 'fastapi', 'httpx')})


class CountingConnection:
    def __init__(self, conn, owner):
        self.conn, self.owner = conn, owner
    def __enter__(self):
        self.conn.__enter__()
        return self
    def __exit__(self, *args):
        return self.conn.__exit__(*args)
    def execute(self, *args):
        cursor = self.conn.execute(*args)
        owner = self.owner
        class Result:
            def fetchall(self):
                rows = cursor.fetchall()
                owner.materialized += len(rows)
                return rows
        return Result()


def process_measurement(label):
    """Fresh Linux process per variant; no tracemalloc in timed/RSS measurement."""
    store = counted(PreviousStore if label == 'previous' else PostgresStore)
    timings = {}
    original_connect = store._connect
    def connect():
        connection = original_connect()
        original_execute = connection.execute
        def execute(*args):
            started = time.perf_counter()
            cursor = original_execute(*args)
            timings['execute_seconds'] = time.perf_counter() - started
            original_fetchall = cursor.fetchall
            def fetchall():
                started = time.perf_counter()
                rows = original_fetchall()
                timings['fetch_decode_seconds'] = time.perf_counter() - started
                return rows
            cursor.fetchall = fetchall
            return cursor
        connection.execute = execute
        return connection
    store._connect = connect
    def rss(field='VmRSS'):
        return int(next(line.split()[1] for line in Path('/proc/self/status').read_text().splitlines()
                        if line.startswith(field + ':'))) * 1024
    before_rss = rss()
    # /proc VmHWM belongs to this exec's address space. ru_maxrss may retain
    # the spawning test process's larger peak across fork/exec on Linux.
    before_peak = rss('VmHWM')
    started = time.perf_counter()
    rows = store.list('incident', 50, 100)
    elapsed = time.perf_counter() - started
    after_rss = rss()
    peak = rss('VmHWM')
    return dict(timings, list_seconds=elapsed, rss_before_bytes=before_rss,
                rss_after_bytes=after_rss, process_peak_rss_before_bytes=before_peak,
                process_peak_rss_bytes=peak, materialized_rows=store.materialized,
                returned_rows=len(rows),
                result_sha256=hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest())


def counted(cls):
    class Counted(cls):
        materialized = 0
        def _connect(self):
            return CountingConnection(super()._connect(), self)
    return Counted(DSN)


class PostgreSQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old, cls.new = PreviousStore(DSN), PostgresStore(DSN)
        with psycopg.connect(DSN) as conn:
            assert conn.execute('SELECT current_database()').fetchone()[0] == 'p11_pagination_test'
            REPORT['version'] = conn.execute('SELECT version()').fetchone()[0]
            REPORT['server_version_num'] = int(conn.execute('SHOW server_version_num').fetchone()[0])
            if REPORT['server_version_num'] != 180006:
                raise RuntimeError('This validation requires exactly PostgreSQL 18.6')
            REPORT['settings'] = dict(conn.execute("SELECT name,setting FROM pg_settings WHERE name IN ('TimeZone','server_encoding','lc_collate','lc_ctype','work_mem','shared_buffers')"))
            REPORT['database_locale'] = conn.execute('SELECT datcollate,datctype FROM pg_database WHERE datname=current_database()').fetchone()
            REPORT['code_sha256'] = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                                     for path in [ROOT / 'postgres_store.py', Path(__file__).parent / 'fixtures/previous_store.py']}
            conn.execute('CREATE TABLE projections(kind text NOT NULL,id text NOT NULL,revision integer NOT NULL,source text NOT NULL,data jsonb NOT NULL,created_at timestamptz NOT NULL,PRIMARY KEY(kind,id,revision))')
            conn.execute('CREATE TABLE audit(seq bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,actor text,operation text,entity text,at timestamptz)')

    def setUp(self):
        with psycopg.connect(DSN) as conn:
            conn.execute('TRUNCATE projections, audit')

    def put(self, kind, id, rev=1, data=None, at='2026-10-26T12:00:00Z'):
        with psycopg.connect(DSN) as conn:
            conn.execute('INSERT INTO projections VALUES(%s,%s,%s,%s,%s,%s)',
                         (kind, id, rev, 'synthetic', Jsonb(data or {'synthetic_test': True}), at))

    def same(self, kind, limit=50, offset=0):
        before = self.old.list(kind, limit, offset)
        after = self.new.list(kind, limit, offset)
        self.assertEqual(before, after)
        return after

    def test_empty_and_validation(self):
        self.assertEqual(self.same('incident'), [])
        for limit in (0, -1, True, None, 1.5, '50', 2**63):
            with self.assertRaises(ValueError): self.new.list('incident', limit)
        for offset in (-1, False, None, 0.5, '0', 2**63):
            with self.assertRaises(ValueError): self.new.list('incident', 50, offset)
        with self.assertRaises(ValueError): self.new.list("incident' OR true --")
        with self.assertRaises(ValueError): self.new.history('invalid', 'x')
        self.assertEqual(self.same('incident', 1001), [])
        self.assertEqual(self.same('incident', 2**63-1, 2**63-1), [])

    def test_latest_kind_ties_unicode_history_and_pages(self):
        for id in ['SYNTHETIC-a', 'SYNTHETIC-Z', 'SYNTHETIC-á', 'SYNTHETIC-z']:
            self.put('incident', id, 1, {'status': 'OPEN'}, '2026-10-27T12:00:00Z')
            # Latest means revision, even when its timestamp is older.
            self.put('incident', id, 2, {'status': 'CLOSED'})
            self.put('decision', id, 1)
        for limit in (1, 2, 50, 200, 1001):
            for offset in (0, 1, 3, 4, 100): self.same('incident', limit, offset)
        self.assertTrue(all(r['revision'] == 2 for r in self.same('incident')))
        self.same('decision')
        self.assertEqual(self.old.history('incident', 'SYNTHETIC-a'), self.new.history('incident', 'SYNTHETIC-a'))
        self.assertEqual(self.new.history('incident', 'absent'), [])
        self.assertEqual([r['revision'] for r in self.new.history('incident', 'SYNTHETIC-a')], [1, 2])

    def test_timezone_and_dst_order(self):
        for i, at in enumerate(['2018-02-18T01:30:00Z', '2018-02-18T02:15:00Z',
                                '2018-02-18T02:30:00Z', '2026-10-26T12:00:00Z',
                                '2026-10-26T12:00:00.000001Z', '2026-10-26T12:00:00.100000Z']):
            self.put('incident', f'SYNTHETIC-{i}', at=at)
        for zone in ('UTC', 'America/Sao_Paulo', 'America/New_York', 'Asia/Kathmandu'):
            a = PreviousStore(DSN + f" options='-c timezone={zone}'")
            b = PostgresStore(DSN + f" options='-c timezone={zone}'")
            self.assertEqual(a.list('incident'), b.list('incident'))

    def test_insert_unchanged(self):
        item = SimpleNamespace(id='SYNTHETIC-insert', revision=1, source='synthetic', data={'a': 1})
        self.assertTrue(self.new.insert('asset', item))
        self.assertFalse(self.new.insert('asset', item))
        with self.assertRaises(ValueError):
            self.new.insert('asset', SimpleNamespace(**{**vars(item), 'data': {'a': 2}}))
        self.same('asset')

    def test_api_and_explanation_filters_after_latest_and_page(self):
        self.put('incident', 'SYNTHETIC-incident', data={'status': 'OPEN'})
        self.put('decision', 'SYNTHETIC-old-match', 1, {'incident_id': 'SYNTHETIC-incident', 'incident_revision': 1})
        self.put('decision', 'SYNTHETIC-old-match', 2, {'incident_id': 'OTHER', 'incident_revision': 1})
        self.put('decision', 'SYNTHETIC-match', data={'incident_id': 'SYNTHETIC-incident', 'incident_revision': 1, 'status': 'OBSERVE_ONLY'})
        self.put('execution', 'SYNTHETIC-exec', data={'decision_id': 'SYNTHETIC-match', 'status': 'SIMULATED'})
        def normalized(store):
            result = explain(store, 'SYNTHETIC-incident')
            result.pop('generated_at')
            return result
        self.assertEqual(normalized(self.old), normalized(self.new))
        self.assertEqual(normalized(self.new)['facts']['execution_status'], 'SIMULATED')
        app = create_app(self.new, 'synthetic-admin', 'synthetic-password')
        install_deterministic_harpia(app, self.new)
        client = TestClient(app)
        self.assertEqual(client.get('/api/v1/p11/incident').status_code, 401)
        client.auth = ('synthetic-admin', 'synthetic-password')
        self.assertEqual(client.get('/api/v1/p11/incident').json(), self.new.list('incident'))
        self.assertEqual(client.get('/api/v1/p11/incident/SYNTHETIC-incident/history').json(), self.new.history('incident', 'SYNTHETIC-incident'))
        self.assertEqual(client.get('/api/v1/p11/explain/SYNTHETIC-incident').json()['facts'], normalized(self.new)['facts'])
        for query in ('limit=0', 'limit=-1', 'limit=201', 'offset=-1', 'limit=x'):
            self.assertEqual(client.get('/api/v1/p11/incident?' + query).status_code, 422)
        # Sentinel overflow must retain unknown, even with an exact match present.
        with psycopg.connect(DSN) as conn:
            conn.execute("INSERT INTO projections SELECT 'decision','SYNTHETIC-overflow-'||g,1,'synthetic','{}'::jsonb,now() FROM generate_series(1,1001) g")
        self.assertEqual(normalized(self.old), normalized(self.new))
        self.assertNotIn('decision_id', normalized(self.new)['facts'])

    def test_volume(self):
        with psycopg.connect(DSN) as conn:
            conn.execute("""INSERT INTO projections
                SELECT 'incident','SYNTHETIC-volume-'||lpad(g::text,6,'0'),r,'synthetic',
                       jsonb_build_object('synthetic_test',true,'padding',repeat('x',2048)),
                       '2026-10-26T12:00:00Z'::timestamptz + (g % 100) * interval '1 second'
                FROM generate_series(1,20000) g CROSS JOIN generate_series(1,3) r""")
            conn.execute('ANALYZE projections')
            REPORT['indexes'] = [r[0] for r in conn.execute("SELECT indexdef FROM pg_indexes WHERE tablename='projections'")]
        samples = {}
        for label, cls in [('previous', PreviousStore), ('new', PostgresStore)]:
            store = counted(cls)
            tracemalloc.start()
            started = time.perf_counter()
            rows = store.list('incident', 50, 100)
            elapsed = time.perf_counter() - started
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            samples[label] = dict(seconds=round(elapsed, 6), peak_python_bytes=peak,
                                  materialized_rows=store.materialized,
                                  returned_rows=len(rows), result_sha256=hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest())
        self.assertEqual(samples['previous']['result_sha256'], samples['new']['result_sha256'])
        self.assertEqual(samples['previous']['materialized_rows'], 20000)
        self.assertEqual(samples['new']['materialized_rows'], 50)
        REPORT['volume'] = dict(total_revisions=60000, latest_ids=20000, limit=50, offset=100, samples=samples)
        # Three fresh processes per variant, alternating order to expose variance.
        process_samples = {'previous': [], 'new': []}
        for labels in [('previous', 'new'), ('new', 'previous'), ('previous', 'new')]:
            for label in labels:
                sample = json.loads(subprocess.check_output([sys.executable, __file__, '--measure', label], text=True))
                self.assertEqual(sample['result_sha256'], samples['new']['result_sha256'])
                self.assertEqual(sample['materialized_rows'], 20000 if label == 'previous' else 50)
                process_samples[label].append(sample)
        REPORT['volume']['fresh_process_samples'] = process_samples
        # Capture the actual statement and parameters without a second SQL copy.
        class Capture:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def execute(self, sql, params):
                self.sql, self.params = sql, params
                return self
            def fetchall(self): return []
        REPORT['explain_analyze'] = {}
        for label, cls in [('previous', PreviousStore), ('new', PostgresStore)]:
            capture = Capture()
            store = cls(DSN)
            store._connect = lambda: capture
            store.list('incident', 50, 100)
            with psycopg.connect(DSN) as conn:
                REPORT['explain_analyze'][label] = dict(sql=capture.sql, parameters=capture.params,
                    plan=conn.execute('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + capture.sql, capture.params).fetchone()[0])


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--measure' and sys.argv[2] in ('previous', 'new'):
        print(json.dumps(process_measurement(sys.argv[2])))
        sys.exit(0)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PostgreSQLTests)
    REPORT['test_cases'] = [test.id() for test in suite]
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    REPORT.update(tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors))
    Path(ROOT / 'TEST_RESULTS.json').write_text(json.dumps(REPORT, indent=2) + '\n')
    sys.exit(not result.wasSuccessful())
