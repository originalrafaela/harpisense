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
            if not isinstance(items, list):
                present.discard(source)
                continue
            for item in items:
                if (not isinstance(item, dict) or not isinstance(item.get('id'), str)
                        or item.get('state') not in CLOSED | ACTIVE):
                    present.discard(source)
                    continue
                if item['state'] in ACTIVE:
                    # Visibility loss must not erase a previously identified active case.
                    blockers.append({'id': source + ':' + item['id'], 'state': item['state'],
                                     'source': source, 'fresh': fresh})
        # Human assessments are durable facts, never a claim that source coverage
        # is complete. Use the same lock as mode changes and preserve a confirmed
        # attack until explicitly reassessed or its incident is closed.
        relation = tx.conn.execute("SELECT to_regclass('hs_incident_assessment')").fetchone()[0]
        if relation:
            assessed = tx.conn.execute("WITH latest AS (SELECT DISTINCT ON(incident_id) incident_id,assessment "
                "FROM hs_incident_assessment ORDER BY incident_id,id DESC), incidents AS "
                "(SELECT DISTINCT ON(id) id,data FROM projections WHERE kind='incident' ORDER BY id,revision DESC) "
                "SELECT a.incident_id FROM latest a LEFT JOIN incidents i ON i.id=a.incident_id "
                "WHERE a.assessment='confirmed' AND coalesce(i.data->>'status','UNKNOWN')<>'CLOSED'").fetchall()
            blockers.extend({'id':'attack:'+row[0], 'state':'CONFIRMED', 'source':'attack', 'fresh':True} for row in assessed)
        missing = sorted(SOURCES - present)
        counts = {source:sum(b['source']==source for b in blockers) for source in sorted(SOURCES|{'attack'})}
        return {'reliable': not missing, 'blockers': blockers,
                'counts':counts,'missing_sources':missing,
                'coverage':'current' if not missing else ('partial' if present else 'unknown'),
                **({'dependency': 'Fontes autoritativas ausentes ou desatualizadas: ' + ', '.join(missing)} if missing else {})}
