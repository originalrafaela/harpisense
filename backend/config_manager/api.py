"""Explicit composition with the existing administrative session dependency."""
import json
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.exceptions import RequestValidationError
from jsonschema import Draft202012Validator

from .schema import ConfigError, REQUEST_SCHEMA, checked, obj
from .store import Conflict
from .setup import FIRMWARE, SAVE_SCHEMA, SetupStore


class SafeRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe(request):
            try:
                response = await handler(request)
            except Conflict as exc:
                response = JSONResponse({'error': {'code': str(exc), 'current_revision': exc.current_revision}}, status_code=409)
            except ConfigError as exc:
                code = str(exc)
                response = JSONResponse({'error': {'code': code, 'fields': field_errors(code)}},
                                        status_code=404 if code.endswith('_NOT_FOUND') else 422)
            except RequestValidationError:
                response = JSONResponse({'error': {'code': 'INVALID_REQUEST'}}, status_code=422)
            response.headers['Cache-Control'] = 'no-store'
            return response
        return safe


def field_errors(code):
    fields = {
        'INCOMPLETE_MQTT_CONFIG': ['parameters.mqtt_broker_host', 'parameters.mqtt_tls_mode', 'parameters.mqtt_ca_ref', 'parameters.mqtt_identity_secret_ref', 'parameters.mqtt_topics', 'parameters.mqtt_client_id', 'parameters.mqtt_broker_port'],
        'INVALID_BROKER_HOST': ['parameters.mqtt_broker_host'],
        'NETWORK_SENSOR_BINDING_REQUIRED': ['parameters.network_cidrs', 'parameters.sensor_bindings'],
        'AMBIGUOUS_NETWORKS': ['parameters.network_cidrs'],
        'AMBIGUOUS_SENSOR_BINDING': ['parameters.sensor_bindings'],
        'FEATURE_SCHEMA_REQUIRED': ['parameters.feature_schema_version'],
        'TOPIC_OUTSIDE_ACL': ['parameters.mqtt_topics'],
        'NETWORK_OUTSIDE_SCOPE': ['parameters.network_cidrs'],
        'UNKNOWN_SENSOR': ['parameters.sensor_bindings'],
        'UNKNOWN_SECRET_REFERENCE': ['parameters.mqtt_identity_secret_ref', 'parameters.external_credential_ref', 'parameters.vpn_auth_ref'],
        'UNSUPPORTED_REFERENCE': ['parameters.mqtt_ca_ref', 'parameters.mqtt_broker_host', 'parameters.capture_filter_profile', 'parameters.protocol_adapter_ref'],
        'INCOMPATIBLE_MODEL': ['parameters.rf_model_ref', 'parameters.if_model_ref'],
        'INVALID_CONFIG_VALUE': ['parameters.timezone', 'parameters.network_cidrs', 'parameters.sensor_bindings'],
    }.get(code, ['$'])
    return [{'field': f, 'code': code} for f in fields]


async def body(request, schema):
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > 65536:
            return JSONResponse({'error': {'code': 'DOCUMENT_TOO_LARGE'}}, status_code=413)
        chunks.append(chunk)
    try:
        value = json.loads(b''.join(chunks))
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise ConfigError('INVALID_JSON') from None
    # Only emit paths derived from schema properties, never unknown submitted keys.
    errors = []
    for error in Draft202012Validator(schema).iter_errors(value):
        path, node = [], schema
        for part in error.absolute_path:
            if isinstance(part, int) and 'items' in node:
                path.append(str(part)); node = node['items']
            elif part in node.get('properties', {}):
                path.append(part); node = node['properties'][part]
            else:
                break
        errors.append({'field': '.'.join(path) or '$', 'code': 'INVALID_FIELD'})
    if errors:
        return JSONResponse({'error': {'code': 'INVALID_REQUEST', 'fields': errors[:64]}}, status_code=422)
    return checked(value, schema)


def install_config_api(app, store, *, installation_id):
    """Call after install_admin_auth. Installation scope is server supplied."""
    require_admin = getattr(app.state, 'require_admin_session', None)
    if require_admin is None or getattr(app.state, 'config_api_installed', False):
        raise RuntimeError('Existing admin session installation required; install once')
    setup = SetupStore(store)
    router = APIRouter(prefix='/api/v1/config', route_class=SafeRoute,
                       dependencies=[Depends(require_admin)])

    def operation(operation_id):
        try:
            key = UUID(operation_id)
        except ValueError:
            raise ConfigError('OPERATION_NOT_FOUND') from None
        with store.connect() as conn, conn.cursor() as cur:
            cur.execute('SELECT revision FROM hs_config.operation WHERE operation_id=%s AND installation_id=%s',
                        (key, installation_id))
            row = cur.fetchone()
        if not row:
            raise ConfigError('OPERATION_NOT_FOUND')
        return store.revision(installation_id, row[0])

    @router.get('/current')
    def current():
        result = store.current(installation_id)
        result['state'] = {'DRAFT': 'draft_saved', 'VALIDATED': 'validated', 'APPLYING': 'application_pending',
                           'APPLIED': 'applied_verified', 'REJECTED': 'failed', 'FAILED': 'failed',
                           'RECOVERY_REQUIRED': 'failed'}.get(result['proposed_status'], 'not_started')
        result['operational'] = False  # This stage has no readiness verifier.
        result['applicability'] = 'not_applicable_no_real_applicators'
        return result

    @router.post('/proposals')
    async def propose(request: Request, actor=Depends(require_admin)):
        value = await body(request, REQUEST_SCHEMA)
        if isinstance(value, JSONResponse): return value
        # Single administrative account id stays stable when its username changes.
        return store.propose(installation_id, 'admin-account-1', value)

    @router.get('/proposals/{operation_id}')
    def proposal(operation_id: str):
        return operation(operation_id)

    @router.post('/proposals/{operation_id}/validate')
    async def validate(operation_id: str, request: Request):
        value = await body(request, obj({'expected_revision': {'type': 'integer', 'minimum': 0}}))
        if isinstance(value, JSONResponse): return value
        operation(operation_id)
        return store.validate(UUID(operation_id), 'admin-account-1', value['expected_revision'])

    @router.get('/history')
    def history(after: int = 0, limit: int = 100):
        return store.history(installation_id, after=after, limit=limit)

    @router.get('/setup')
    def resume():
        return setup.get(installation_id)

    @router.put('/setup')
    async def save(request: Request):
        value = await body(request, SAVE_SCHEMA)
        if isinstance(value, JSONResponse): return value
        return setup.save(installation_id, 'admin-account-1', value)

    @router.get('/catalog')
    def catalog():
        return {'firmware_profiles': FIRMWARE, 'deployment_profiles': ['esp32-lighting'],
                'applicators': [], 'backup': 'not_applicable', 'bootstrap_managed': False}

    app.include_router(router)
    app.state.config_api_installed = True
    app.openapi_schema = None
