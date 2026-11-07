"""Composite adapter for server-owned operational authorities, never P11 reads.

Each source receives the SAME PostgreSQL connection under Controls' lock and
returns {reliable: bool, items: [{id, state}]}. A missing authority fails closed.
Producers must acquire Controls.decision_transaction for every lifecycle write.
"""

STATES = {
    'anomaly': ({'ACTIVE'}, {'CLOSED'}),
    'incident': ({'OBSERVED', 'SUSPECTED', 'CORROBORATED'}, {'CLOSED'}),
    'approval': ({'REQUEST_APPROVAL', 'PENDING', 'APPROVED'}, {'DENIED', 'EXPIRED', 'CONSUMED', 'CANCELLED'}),
    'execution': ({'QUEUED', 'APPLYING', 'COMMAND_ACCEPTED', 'VERIFYING', 'MITIGATION_CONFIRMED',
                   'UNKNOWN_OUTCOME', 'EXPIRING', 'REVERSING', 'REVERSAL_FAILED'},
                  {'SIMULATED', 'UNAVAILABLE', 'FAILED', 'EXPIRED', 'REVERSED'}),
}


class AuthorityQueue:
    def __init__(self, sources):
        self.sources = dict(sources)

    def snapshot(self, tx):
        reliable, blockers, unknown = True, [], []
        for domain, (active, closed) in STATES.items():
            source = self.sources.get(domain)
            try:
                snapshot = source(tx.conn) if source else None
                if not isinstance(snapshot, dict) or snapshot.get('reliable') is not True or not isinstance(snapshot.get('items'), list):
                    raise ValueError('Authority unavailable')
                for item in snapshot['items']:
                    if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item['id'] or item.get('state') not in active | closed:
                        raise ValueError('Unknown lifecycle')
                    if item['state'] in active:
                        blockers.append({'domain': domain, 'id': item['id'], 'state': item['state']})
            except Exception:
                reliable = False
                unknown.append(domain)
        return {'reliable': reliable, 'blockers': blockers, 'unknown_domains': unknown,
                'dependency': 'Operational authorities must be complete and share the controls transaction.'}
