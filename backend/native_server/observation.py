"""Durable observations from the actual installer-owned consumer, not drafts."""
import psycopg
from psycopg.rows import dict_row


def heartbeat(state, connected, subscribed):
    with psycopg.connect(state['dsn']) as conn:
        conn.execute('''INSERT INTO hs_native_mqtt_observation(installation_id,connected,subscribed)
            VALUES(%s,%s,%s) ON CONFLICT(installation_id) DO UPDATE SET
            connected=excluded.connected,subscribed=excluded.subscribed,observed_at=clock_timestamp()''',
            (state['installation_id'], connected, subscribed))


def message_received(state, message, projection_id):
    with psycopg.connect(state['dsn']) as conn:
        # QoS retries must not turn an old sample into fresh telemetry. The exact
        # immutable revision supplies its original ingestion time, not retry time.
        conn.execute('''UPDATE hs_native_mqtt_observation AS o SET last_message_id=%s,
            last_projection_id=%s,last_message_at=p.created_at FROM projections AS p
            WHERE o.installation_id=%s AND p.kind='telemetry' AND p.id=%s AND p.revision=1
            AND (o.last_message_at IS NULL OR p.created_at >= o.last_message_at)''',
            (message, projection_id, state['installation_id'], projection_id))


def mqtt_observation(state):
    from config_manager.mqtt import mqtt_status
    result = mqtt_status()
    with psycopg.connect(state['dsn'], row_factory=dict_row) as conn:
        row = conn.execute('SELECT *,clock_timestamp() AS now FROM hs_native_mqtt_observation WHERE installation_id=%s',
                           (state['installation_id'],)).fetchone()
    return project_observation(state, row, result)


def project_observation(state, row, result):
    """Read-only MQTT coverage, never an incident assessment or profile gate.

    The telemetry TTL is an observation policy, not a device sampling promise.
    Only the ACL-bound poste2 stream is covered by this runtime composition.
    """
    ttl = state['mqtt'].get('telemetry_max_age_seconds', 120)
    if type(ttl) is not int or ttl <= 0:
        raise ValueError('INVALID_TELEMETRY_MAX_AGE_SECONDS')
    result['coverage'] = {
        'scope': 'mqtt_telemetry', 'state': 'unknown',
        'expected_device_ids': ['poste2'], 'fresh_device_ids': [],
        'telemetry_max_age_seconds': ttl,
        'incident_state': 'unknown',
        'missing_links': ['window_id', 'detection_id', 'incident_id', 'source_origin'],
    }
    # Presence of application state alone never claims a third-party component installed.
    if state['mqtt']['mode'] == 'local_managed' and state.get('installed_at'):
        result['component'] = {'state': 'installed', 'observed_at': state['installed_at']}
    if row is None:
        return result
    stamp = row['observed_at'].isoformat()
    fresh = 0 <= (row['now'] - row['observed_at']).total_seconds() <= 45
    ready = fresh and row['connected'] and row['subscribed']
    result['broker'] = {'state': 'available' if fresh and row['connected'] else 'not_verified', 'observed_at': stamp}
    result['consumer'] = {'state': 'connected' if fresh and row['connected'] and row['subscribed'] else 'not_verified',
                          'observed_at': stamp}
    if ready:
        result['reason_code'] = 'MESSAGE_RECEIVED' if row['last_message_at'] else 'AWAITING_FIRST_MESSAGE'
    else:
        result['reason_code'] = 'CONSUMER_OBSERVATION_STALE_OR_DISCONNECTED'
    # This version observes only the explicitly ACL-bound Poste 2 identity.
    result['inventory'] = ['poste2']
    if row['last_message_at']:
        age = (row['now'] - row['last_message_at']).total_seconds()
        telemetry_fresh = 0 <= age <= ttl
        available = ready and telemetry_fresh
        result['device_observation'] = 'observed' if available else 'not_verified'
        result['coverage']['state'] = 'complete' if available else 'partial'
        result['coverage']['fresh_device_ids'] = ['poste2'] if available else []
        if ready and not telemetry_fresh:
            result['reason_code'] = 'TELEMETRY_STALE' if age >= 0 else 'TELEMETRY_TIMESTAMP_IN_FUTURE'
        result['devices'] = [{'device_id': 'poste2', 'message_id': row['last_message_id'],
            'projection_id': row['last_projection_id'], 'observed_at': row['last_message_at'].isoformat(),
            'projection_revision': 1,
            'timestamp_basis': 'consumer_received_at',
            'freshness': 'fresh' if telemetry_fresh else 'stale' if age >= 0 else 'unknown',
            'availability': 'available' if available else 'unknown',
            'source_origin': 'unknown',
            'origin': 'authenticated_mqtt_consumer'}]
    return result
