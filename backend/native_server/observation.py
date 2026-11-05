"""Durable observations from the actual installer-owned consumer, not drafts."""
from datetime import datetime, timezone
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
        conn.execute('''UPDATE hs_native_mqtt_observation SET last_message_id=%s,
            last_projection_id=%s,last_message_at=clock_timestamp() WHERE installation_id=%s''',
            (message, projection_id, state['installation_id']))


def mqtt_observation(state):
    from config_manager.mqtt import mqtt_status
    result = mqtt_status()
    with psycopg.connect(state['dsn'], row_factory=dict_row) as conn:
        row = conn.execute('SELECT *,clock_timestamp() AS now FROM hs_native_mqtt_observation WHERE installation_id=%s',
                           (state['installation_id'],)).fetchone()
    # Presence of application state alone never claims a third-party component installed.
    if state['mqtt']['mode'] == 'local_managed' and state.get('installed_at'):
        result['component'] = {'state': 'installed', 'observed_at': state['installed_at']}
    if row is None:
        return result
    stamp = row['observed_at'].isoformat()
    fresh = (row['now'] - row['observed_at']).total_seconds() <= 45
    result['broker'] = {'state': 'available' if fresh and row['connected'] else 'not_verified', 'observed_at': stamp}
    result['consumer'] = {'state': 'connected' if fresh and row['connected'] and row['subscribed'] else 'not_verified',
                          'observed_at': stamp}
    if fresh and row['subscribed'] and row['connected']:
        result['device_observation'] = 'observed'
        result['reason_code'] = 'MESSAGE_RECEIVED' if row['last_message_at'] else 'AWAITING_FIRST_MESSAGE'
    else:
        result['reason_code'] = 'CONSUMER_OBSERVATION_STALE_OR_DISCONNECTED'
    # This version observes only the explicitly ACL-bound Poste 2 identity.
    result['inventory'] = ['poste2']
    if row['last_message_at']:
        result['devices'] = [{'device_id': 'poste2', 'message_id': row['last_message_id'],
            'projection_id': row['last_projection_id'], 'observed_at': row['last_message_at'].isoformat(),
            'origin': 'authenticated_mqtt_consumer'}]
    return result
