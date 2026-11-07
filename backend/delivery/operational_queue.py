"""Fail-closed authoritative snapshots, never inferred from read-only projections.

No browser route writes these reports. Domain workers must publish a complete
source snapshot using Controls.decision_transaction and the same advisory lock.
Until every source is integrated and fresh, changes remain blocked.
"""
SOURCES = frozenset(('incident', 'anomaly', 'approval', 'execution', 'verification'))
CLOSED = frozenset(('CLOSED', 'RESOLVED', 'REJECTED', 'CANCELLED', 'EXPIRED', 'VERIFIED', 'COMPLETED'))
ACTIVE = frozenset(('OPEN', 'ACTIVE', 'PENDING', 'REQUEST_APPROVAL', 'APPROVED', 'RUNNING', 'ACCEPTED', 'VERIFYING', 'UNKNOWN'))


class OperationalQueue:
    def report(self, tx, source, revision, items):
        """Trusted worker hook under Controls.decision_transaction; never HTTP input."""
        from psycopg.types.json import Jsonb
        if (source not in SOURCES or type(revision) is not int or revision < 1
                or not isinstance(items, list) or len(items) > 10000
                or any(not isinstance(i, dict) or not isinstance(i.get('id'), str)
                       or not 1 <= len(i['id']) <= 128 or i.get('state') not in CLOSED | ACTIVE for i in items)):
            raise ValueError('INVALID_OPERATIONAL_SNAPSHOT')
        previous = tx.conn.execute('SELECT revision FROM hs_operational_authority WHERE source=%s FOR UPDATE',
                                   (source,)).fetchone()
        if previous and revision <= previous[0]:
            raise ValueError('STALE_OPERATIONAL_SNAPSHOT')
        tx.conn.execute('INSERT INTO hs_operational_authority(source,revision,items) VALUES(%s,%s,%s) '
                        'ON CONFLICT(source) DO UPDATE SET revision=excluded.revision,items=excluded.items,'
                        'observed_at=clock_timestamp()', (source, revision, Jsonb(items)))

    def snapshot(self, tx):
        rows = tx.conn.execute('SELECT source,items,observed_at>clock_timestamp()-interval \'30 seconds\' '
                               'FROM hs_operational_authority').fetchall()
        present = {row[0] for row in rows if row[2]}
        blockers = []
        for source, items, fresh in rows:
            if not fresh:
                continue
            if not isinstance(items, list):
                present.discard(source)
                continue
            for item in items:
                if (not isinstance(item, dict) or not isinstance(item.get('id'), str)
                        or item.get('state') not in CLOSED | ACTIVE):
                    present.discard(source)
                    continue
                if item['state'] in ACTIVE:
                    blockers.append({'id': source + ':' + item['id'], 'state': item['state']})
        missing = sorted(SOURCES - present)
        return {'reliable': not missing, 'blockers': blockers,
                **({'dependency': 'Fontes autoritativas ausentes ou desatualizadas: ' + ', '.join(missing)} if missing else {})}
