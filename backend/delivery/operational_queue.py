"""Fail-closed authoritative snapshots, never inferred from read-only projections.

No browser route writes these reports. Domain workers must publish a complete
source snapshot using Controls.decision_transaction and the same advisory lock.
Until every source is integrated and fresh, changes remain blocked.
"""
SOURCES = frozenset(('incident', 'anomaly', 'approval', 'execution', 'verification'))
CLOSED = frozenset(('CLOSED', 'RESOLVED', 'REJECTED', 'CANCELLED', 'EXPIRED', 'VERIFIED', 'COMPLETED'))
ACTIVE = frozenset(('OPEN', 'ACTIVE', 'PENDING', 'REQUEST_APPROVAL', 'APPROVED', 'AUTHORIZED',
                    'QUEUED', 'APPLYING', 'RUNNING', 'ACCEPTED', 'COMMAND_ACCEPTED', 'VERIFYING',
                    'UNKNOWN', 'UNKNOWN_OUTCOME', 'EXPIRING', 'REVERSING', 'REVERSAL_FAILED'))
UNKNOWN = frozenset(('UNKNOWN', 'UNKNOWN_OUTCOME'))
CASE_SOURCES = frozenset(('incident', 'anomaly'))


def valid_item(item):
    return (isinstance(item, dict) and isinstance(item.get('id'), str)
            and 1 <= len(item['id']) <= 128 and item.get('state') in CLOSED | ACTIVE)


def summarize(rows):
    """Pure projection of authoritative reports; stale active facts are retained.

    Counts refer to source items, never guessed cross-source incident links.
    A source snapshot revision is exposed separately from any item revision.
    """
    present, blockers, sources, known_cases = set(), [], [], []
    case_complete = set()
    for source, items, fresh, revision, observed_at in rows:
        if source not in SOURCES:
            continue
        valid = (isinstance(items, list) and all(valid_item(item) for item in items)
                 and len({item['id'] for item in items}) == len(items))
        certain = valid and not any(item['state'] in UNKNOWN for item in items)
        current = fresh is True and certain
        if current:
            present.add(source)
            if source in CASE_SOURCES:
                case_complete.add(source)
        sources.append({'source': source, 'source_revision': revision,
                        'observed_at': observed_at.isoformat() if hasattr(observed_at, 'isoformat') else observed_at,
                        'fresh': fresh is True, 'valid': valid, 'complete': current})
        # Even a partially malformed report must not erase its valid active facts.
        seen = set()
        for item in items if isinstance(items, list) else []:
            if valid_item(item) and item['state'] in ACTIVE:
                if item['id'] in seen:
                    continue
                seen.add(item['id'])
                blocker = {'id': source + ':' + item['id'], 'state': item['state'],
                           'source': source, 'record_id': item['id'],
                           'source_revision': revision, 'fresh': fresh is True}
                if type(item.get('revision')) is int and item['revision'] > 0:
                    blocker['record_revision'] = item['revision']
                blockers.append(blocker)
                if source in CASE_SOURCES and item['state'] not in UNKNOWN:
                    known_cases.append(blocker)
    supplied = {s['source'] for s in sources}
    sources.extend({'source': source, 'source_revision': None, 'observed_at': None,
                    'fresh': False, 'valid': False, 'complete': False}
                   for source in sorted(SOURCES - supplied))
    missing = sorted(SOURCES - present)
    coverage = 'complete' if case_complete == CASE_SOURCES else 'partial' if case_complete else 'unknown'
    status = 'active' if known_cases else 'none_active' if coverage == 'complete' else coverage
    return {'reliable': not missing, 'blockers': blockers,
            'cases': {'status': status, 'known_active_count': len(known_cases),
                      'count_basis': 'source_item', 'coverage': coverage,
                      'sources': sorted((s for s in sources if s['source'] in CASE_SOURCES), key=lambda s: s['source']),
                      'items': known_cases},
            'sources': sorted(sources, key=lambda s: s['source']),
            **({'dependency': 'Fontes autoritativas ausentes, desconhecidas ou desatualizadas: ' + ', '.join(missing)} if missing else {})}


class OperationalQueue:
    def report(self, tx, source, revision, items):
        """Trusted worker hook under Controls.decision_transaction; never HTTP input."""
        from psycopg.types.json import Jsonb
        if (source not in SOURCES or type(revision) is not int or revision < 1
                or not isinstance(items, list) or len(items) > 10000
                or any(not valid_item(i) for i in items)
                or len({i['id'] for i in items}) != len(items)):
            raise ValueError('INVALID_OPERATIONAL_SNAPSHOT')
        previous = tx.conn.execute('SELECT revision,items FROM hs_operational_authority WHERE source=%s FOR UPDATE',
                                   (source,)).fetchone()
        if previous and revision <= previous[0]:
            raise ValueError('STALE_OPERATIONAL_SNAPSHOT')
        # A heartbeat with no items is not an explicit case closure or queue result.
        if previous:
            prior = previous[1]
            if not isinstance(prior, list) or any(not valid_item(i) for i in prior):
                raise ValueError('INVALID_PREVIOUS_OPERATIONAL_SNAPSHOT')
            retained = {i['id'] for i in items}
            if any(i['state'] in ACTIVE and i['id'] not in retained for i in prior):
                raise ValueError('ACTIVE_ITEM_REQUIRES_CLOSURE')
        tx.conn.execute('INSERT INTO hs_operational_authority(source,revision,items) VALUES(%s,%s,%s) '
                        'ON CONFLICT(source) DO UPDATE SET revision=excluded.revision,items=excluded.items,'
                        'observed_at=clock_timestamp()', (source, revision, Jsonb(items)))

    def snapshot(self, tx):
        rows = tx.conn.execute('SELECT source,items,observed_at>clock_timestamp()-interval \'30 seconds\',revision,observed_at '
                               'FROM hs_operational_authority').fetchall()
        return summarize(rows)
