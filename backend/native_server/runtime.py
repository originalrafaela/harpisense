"""Shared Windows/Ubuntu runtime, with explicit installer-owned state."""
import json
import os
import ssl
import threading
import time
from pathlib import Path

import psycopg
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from admin_auth.candidate import install_candidate_admin_auth
from config_manager.api import install_config_api
from config_manager.schema import Capabilities
from config_manager.store import ConfigStore
from delivery.app import build_app
from delivery.mqtt_consumer import bind_consumer
from delivery.postgres_store import PostgresStore


def load_state(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise RuntimeError('INSTALLATION_STATE_UNAVAILABLE')
    path = path.resolve()
    state = json.loads(path.read_text(encoding='utf-8'))
    if state.get('schema') != 1:
        raise RuntimeError('INSTALLATION_STATE_VERSION')
    return state


def environment(state):
    os.environ.update(DATABASE_URL=state['dsn'],
        HARPISENSE_ADMIN_USER=state['technical_user'],
        HARPISENSE_ADMIN_PASSWORD=state['technical_password'],
        HARPISENSE_PROJECTION_SERVICE_TOKEN=state['projection_token'])


def capabilities(state):
    mqtt = state['mqtt']
    return Capabilities(revision='native-v1',
        mqtt_hosts=frozenset([mqtt['host']]), mqtt_topics=frozenset(mqtt['topics']),
        ca_refs=frozenset(['native-mqtt-ca']),
        secret_refs=frozenset(['secret://native/mqtt-consumer']))


def build_native_app(state, frontend):
    environment(state)
    api = build_app()
    credentials = [(state['technical_user'], state['technical_password']),
                   (state['mqtt']['username'], state['mqtt']['password'])]
    install_candidate_admin_auth(api, state['dsn'],
        protection_key=Path(state['key_file']).read_bytes().strip(),
        allowed_origins=[state['panel_url']], technical_credentials=credentials)
    store = PostgresStore(state['dsn'])
    from .observation import mqtt_observation
    install_config_api(api, ConfigStore(store._connect, capabilities(state)),
                       installation_id=state['installation_id'],
                       mqtt_observer=lambda: mqtt_observation(state))

    @api.get('/api/v1/native/status', dependencies=[Depends(api.state.require_admin_session)])
    def status():
        return {'server': 'installed', 'platform': os.name, 'mqtt_mode': state['mqtt']['mode'],
                'capture': 'not_verified', 'containment': 'not_available',
                'rf': 'not_verified', 'if': 'not_verified', 'operational': False}

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware('http')
    async def local_transport(request, call_next):
        # Reject DNS rebinding and cross-origin writes before auth/DB handlers.
        expected = state['panel_url'].split('://', 1)[1]
        if request.headers.get('host') != expected:
            return JSONResponse({'error': {'code': 'HOST_DENIED'}}, status_code=403)
        origin = request.headers.get('origin')
        if origin and origin != state['panel_url']:
            return JSONResponse({'error': {'code': 'ORIGIN_DENIED'}}, status_code=403)
        if request.url.path.startswith('/p11-api/'):
            # Technical ingestion has no browser transport, as in the Vite guard.
            auth = request.headers.get('authorization', '')
            if auth and not auth.startswith('Bearer '):
                return JSONResponse({'error': {'code': 'AUTH_REQUIRED'}}, status_code=401)
            if '/ingest/' in request.url.path:
                return JSONResponse({'error': {'code': 'NOT_FOUND'}}, status_code=404)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        return response

    app.mount('/p11-api', api)
    app.mount('/', StaticFiles(directory=str(frontend), html=True), name='panel')
    return app


def mqtt_client(state):
    import paho.mqtt.client as mqtt
    cfg = state['mqtt']
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id='harpisense-' + state['installation_id'])
    client.username_pw_set(cfg['username'], cfg['password'])
    client.tls_set(ca_certs=cfg['ca_file'], cert_reqs=ssl.CERT_REQUIRED,
                   tls_version=ssl.PROTOCOL_TLS_CLIENT)
    client.reconnect_delay_set(1, 60)
    return client


def run_consumer(state):
    import hashlib
    from .observation import heartbeat, message_received
    client = mqtt_client(state)
    adapter = bind_consumer(client, PostgresStore(state['dsn']), lambda code: print(code, flush=True))
    connected, subscribed, stopping = threading.Event(), threading.Event(), threading.Event()
    original_connect, original_message = client.on_connect, client.on_message
    def on_connect(c, userdata, flags, reason, properties):
        subscribed.clear()
        if not reason.is_failure:
            connected.set()
        else:
            connected.clear()
        original_connect(c, userdata, flags, reason, properties)
        heartbeat(state, connected.is_set(), False)
    def on_subscribe(c, userdata, mid, reasons, properties):
        if reasons and all(not reason.is_failure for reason in reasons):
            subscribed.set()
        heartbeat(state, connected.is_set(), subscribed.is_set())
    def on_disconnect(c, userdata, flags, reason, properties):
        connected.clear()
        subscribed.clear()
        heartbeat(state, False, False)
    def on_message(c, userdata, msg):
        outcome = original_message(c, userdata, msg)
        if outcome in ('inserted', 'duplicate'):
            data = json.loads(msg.payload)
            identity = data.get('message_id')
            if not isinstance(identity, str) or not 1 <= len(identity) <= 128:
                identity = 'sha256:' + hashlib.sha256(msg.payload).hexdigest()
            projection = 'poste2-' + hashlib.sha256(msg.topic.encode() + b'\0' + msg.payload).hexdigest()
            message_received(state, identity, projection)
    def refresh():
        while not stopping.wait(10):
            try:
                heartbeat(state, connected.is_set(), subscribed.is_set())
            except Exception:
                print('MQTT_OBSERVATION_UNAVAILABLE', flush=True)
    client.on_connect, client.on_subscribe = on_connect, on_subscribe
    client.on_disconnect, client.on_message = on_disconnect, on_message
    heartbeat(state, False, False)
    thread = threading.Thread(target=refresh, daemon=True)
    thread.start()
    try:
        client.connect_async(state['mqtt']['host'], state['mqtt']['port'], keepalive=20)
        client.loop_forever(retry_first_connection=True)
    finally:
        stopping.set()
        heartbeat(state, False, False)


def wait_for_broker(state, timeout=30, interval=.25):
    """Wait for a newly started local broker; TLS/auth failures are final."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            return probe_broker(state, timeout=min(10, max(.01, deadline - time.monotonic())))
        except ConnectionRefusedError as error:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError('MQTT_BROKER_START_TIMEOUT') from error
            time.sleep(min(interval, remaining))


def probe_broker(state, timeout=10):
    """Read-only MQTT CONNECT/SUBSCRIBE validation, never administer external broker."""
    connected, subscribed = threading.Event(), threading.Event()
    result = {'connected': False, 'subscribed': False}
    client = mqtt_client(state)
    def on_connect(c, userdata, flags, reason, properties):
        result['connected'] = not reason.is_failure
        connected.set()
        if result['connected']:
            c.subscribe([(topic, 1) for topic in state['mqtt']['topics']])
    def on_subscribe(c, userdata, mid, reasons, properties):
        result['subscribed'] = bool(reasons) and all(not reason.is_failure for reason in reasons)
        subscribed.set()
    client.on_connect, client.on_subscribe = on_connect, on_subscribe
    try:
        client.connect(state['mqtt']['host'], state['mqtt']['port'], 30)
        client.loop_start()
        connected.wait(timeout)
        if result['connected']:
            subscribed.wait(timeout)
        if not all(result.values()):
            raise RuntimeError('MQTT_CONNECT_OR_SUBSCRIBE_REJECTED')
        return result
    finally:
        client.disconnect()
        client.loop_stop()
