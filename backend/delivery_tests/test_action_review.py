"""Policy/review fixtures, never installed OS acceptance."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from test_delivery import MemoryRepository, IsolatedQueue
from policy_fixtures import context, NOW
from delivery.controls import Controls
from delivery.action_review import ActionReview
from harpisense_engines import decide


class ReviewMemory(MemoryRepository):
    def review_get(self, kind, decision_id):
        return deepcopy(self.results.get((kind, decision_id)))

    def review_put(self, kind, decision_id, data, actor):
        self.results[(kind, decision_id)] = deepcopy(data)
        self.log(actor, 'ACTION_' + kind.upper(), data)


class ActionReviewTests(unittest.TestCase):
    def setUp(self):
        self.repo = ReviewMemory()
        self.controls = Controls(self.repo, IsolatedQueue())
        self.controls.change(value=dict(operation='SIMULATION', autonomy_mode=1, execution_enabled=True),
            expected_revision=1, actor='admin-test', reason='isolated fixture')
        self.ctx = context()
        self.bundle = decide(self.ctx, mode=1, now=NOW)
        self.origin = 'synthetic'
        self.incident_revision = 1
        self.workflow = ActionReview(self.controls, self.resolve)
        self.key = self.bundle['decision']['decision_id']

    def resolve(self, tx, key):
        return deepcopy(self.bundle), deepcopy(self.ctx), self.origin, self.incident_revision

    def approve(self, **changes):
        return self.workflow.approve(self.key, **{
            'expected_action': self.bundle['decision']['action_fingerprint'],
            'expected_revision': 2, 'actor': 'admin-test', 'now': NOW, **changes})

    def run_sim(self, **changes):
        return self.workflow.simulate(self.key, **{
            'expected_revision': 2, 'actor': 'admin-test', 'now': NOW, **changes})

    def test_m1_specific_approval_preserves_profile_and_does_not_dispatch(self):
        before = self.repo.read()
        pending = deepcopy(self.bundle)
        approved = self.approve()
        self.assertEqual(self.repo.read(), before)
        self.assertEqual(self.bundle, pending)
        self.assertEqual(approved['historical_profile'], 1)
        self.assertFalse(approved['dispatched'])
        self.assertEqual(approved['origin'], 'synthetic')
        self.assertEqual(set(k[0] for k in self.repo.results), {'approval'})
        self.assertEqual(approved['bundle']['decision']['supersedes_decision_id'], self.key)

    def test_m1_simulation_without_specific_approval_refused(self):
        with self.assertRaises(ValueError): self.run_sim()
        self.assertEqual(self.repo.results, {})

    def test_repeated_simulated_origin_never_invokes_os_and_records_separate_events(self):
        self.approve()
        before = self.repo.read()
        with patch('subprocess.Popen', side_effect=AssertionError('OS executor forbidden')), \
             patch('os.system', side_effect=AssertionError('shell forbidden')):
            first = self.run_sim()
            self.assertEqual(first, self.run_sim())
        self.assertEqual(self.repo.read(), before)
        self.assertEqual(len(self.repo.results), 3)
        self.assertEqual(first['execution']['status'], 'SIMULATED')
        self.assertEqual(first['origin'], 'synthetic')
        self.assertFalse(first['mitigation_confirmed'])
        self.assertEqual(first['historical_profile'], 1)
        kinds = [e['operation'] for e in self.repo.events]
        for kind in ('APPROVAL', 'RESULT', 'VERIFICATION'):
            self.assertEqual(kinds.count('ACTION_' + kind), 1)

    def test_approval_wrong_action_actor_revision_and_expiry_refused(self):
        for changes in ({'expected_action': '0'*64}, {'actor': ''},
                        {'now': '2026-10-15T15:10:12Z'}, {'expected_revision': 1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError if 'expected_revision' not in changes else Exception):
                self.approve(**changes)
        self.assertEqual(self.repo.results, {})

    def test_revalidate_context_target_executor_and_incident_before_result(self):
        self.approve()
        original = deepcopy(self.ctx)
        for field, value in (('verified', False), ('executor_ready', False), ('protected', True)):
            self.ctx = deepcopy(original)
            self.ctx['target'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.run_sim()
        self.ctx = original
        self.incident_revision = 2
        with self.assertRaises(ValueError): self.run_sim()
        self.assertIsNone(self.repo.review_get('result', self.key))

    def test_origin_change_or_unknown_is_not_promoted(self):
        self.approve()
        self.origin = 'trusted-service'
        with self.assertRaisesRegex(ValueError, 'ORIGIN_CONFLICT'): self.run_sim()
        self.origin = 'unknown'
        with self.assertRaisesRegex(ValueError, 'ORIGIN_UNVERIFIED'): self.run_sim()

    def test_m2_and_m3_reuse_canonical_policy_without_implicit_approval(self):
        from harpisense_catalog import CATALOG
        for mode in (1, 2, 3):
            for case, entry in CATALOG.items():
                decision = decide(context(case), mode=mode, now=NOW)['decision']
                manual = mode == 1 or mode == 2 and entry['group'] != 'Low'
                self.assertEqual(decision['status'], 'REQUEST_APPROVAL' if manual else 'AUTHORIZED')

    def test_emergency_blocks_approval_and_result_independently(self):
        self.approve()
        self.controls.stop(actor='admin-test', reason='isolated emergency')
        with self.assertRaisesRegex(ValueError, 'EMERGENCY_STOPPED'): self.approve(expected_revision=3)
        with self.assertRaisesRegex(ValueError, 'SIMULATION_DISABLED'): self.run_sim(expected_revision=3)
