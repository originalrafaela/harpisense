"""Control protocol checks; no projection is treated as operational authority."""
import copy
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'backend'), str(ROOT/'backend/domain'), str(ROOT/'genai')]
from delivery.controls import Controls, Rejected


class Repository:
    def __init__(self):
        self.lock = threading.RLock()
        self.state = dict(value=dict(operation='IDS', execution_enabled=False, autonomy_mode=1),
                          revision=1, emergency_stopped=False, updated_at='2026-11-07T12:00:00Z')
        self.logs = []
        self.results = {}

    @contextmanager
    def transaction(self):
        with self.lock:
            yield self

    def read(self): return copy.deepcopy(self.state)
    def save(self, value, revision, stopped):
        self.state.update(value=value, revision=revision, emergency_stopped=stopped)
    def log(self, *args): self.logs.append(args)
    def simulation_once(self, decision_id, result):
        return self.results.setdefault(decision_id, copy.deepcopy(result))


class Queue:
    def __init__(self): self.items, self.reliable, self.calls = [], True, 0
    def snapshot(self, tx):
        self.calls += 1
        return dict(reliable=self.reliable, blockers=copy.deepcopy(self.items))


class ControlStateTests(unittest.TestCase):
    def setUp(self):
        self.repo, self.queue = Repository(), Queue()
        self.controls = Controls(self.repo, self.queue)

    def apply(self, mode=2, revision=1):
        return self.controls.change(value=dict(operation='IDS', execution_enabled=False, autonomy_mode=mode),
                                    expected_revision=revision, actor='test', reason='test Apply')

    def test_apply_revalidates_after_screen_read_and_returns_current(self):
        self.assertTrue(self.controls.get()['change_allowed'])
        self.queue.items = [dict(id='incident:active', state='ACTIVE')]
        before = self.repo.read()
        with self.assertRaises(Rejected) as caught: self.apply()
        self.assertEqual(self.repo.read(), before)
        self.assertEqual(caught.exception.detail['current']['value'], before['value'])
        self.assertEqual(self.queue.calls, 2)

    def test_unknown_and_malformed_authority_refuse(self):
        for reliable in (False, 'true'):
            self.queue.reliable = reliable
            with self.assertRaises(Rejected) as caught: self.apply()
            self.assertEqual(caught.exception.detail['code'], 'QUEUE_UNVERIFIED')
        self.assertEqual(self.repo.read()['revision'], 1)

    def test_stop_does_not_read_even_broken_authority(self):
        def broken(tx): raise AssertionError('must not consult authority')
        self.queue.snapshot = broken
        state = self.controls.stop(actor='test', reason='test emergency')
        self.assertTrue(state['emergency_stopped'])
        self.assertFalse(state['effective_state']['execution_enabled'])

    def test_profile_and_executor_are_independent_and_history_is_frozen(self):
        with self.controls.decision_transaction(1) as (_, state):
            historical = state['historical_profile']
        applied = self.apply(mode=3)
        self.assertEqual(historical['applied_profile'], 'M1')
        self.assertEqual(historical['control_revision'], 1)
        self.assertEqual(applied['effective_state']['applied_profile'], 'M3')
        self.assertFalse(applied['effective_state']['containment_confirmed'])
        self.assertEqual(applied['effective_state']['availability'], 'real_executor_unavailable')

    def test_concurrent_admission_is_revalidated_under_same_lock(self):
        admitted, release = threading.Event(), threading.Event()
        def admit():
            with self.controls.decision_transaction(1):
                self.queue.items.append(dict(id='approval:pending', state='REQUEST_APPROVAL'))
                admitted.set()
                if not release.wait(5): raise RuntimeError('test timeout')
        with ThreadPoolExecutor(2) as pool:
            writer = pool.submit(admit)
            self.assertTrue(admitted.wait(5))
            applying = pool.submit(self.apply)
            release.set()
            writer.result()
            with self.assertRaises(Rejected): applying.result()
        self.assertEqual(self.repo.read()['revision'], 1)

    def test_two_apply_requests_have_one_winner(self):
        barrier = threading.Barrier(2)
        def apply(mode):
            barrier.wait(5)
            try: return self.apply(mode)['revision']
            except Rejected: return 'conflict'
        with ThreadPoolExecutor(2) as pool:
            self.assertCountEqual(list(pool.map(apply, (2, 3))), [2, 'conflict'])

    def test_trial_result_preserves_origin_and_historical_profile(self):
        from delivery.simulation import simulate
        from harpisense_engines import decide
        from policy_fixtures import context, NOW
        self.controls.change(value=dict(operation='SIMULATION', execution_enabled=True, autonomy_mode=3),
                             expected_revision=1, actor='test', reason='isolated trial')
        evidence = context('C07')
        bundle = decide(evidence, mode=3, now=NOW)
        original = copy.deepcopy((bundle, evidence))
        result = simulate(self.controls, bundle, evidence, expected_revision=2, now=NOW)
        self.assertEqual((bundle, evidence), original)
        self.assertEqual(result['historical_profile']['applied_profile'], 'M3')
        self.assertEqual(result['historical_profile']['control_revision'], 2)
        self.assertTrue(result['trial']['simulated'])
        self.assertFalse(result['mitigation_confirmed'])
        self.apply(mode=1, revision=2)
        self.assertEqual(self.repo.results[bundle['decision']['decision_id']]['historical_profile'],
                         result['historical_profile'])


if __name__ == '__main__': unittest.main()
