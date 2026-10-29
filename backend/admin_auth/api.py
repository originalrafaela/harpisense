"""Explicit installer for FastAPI 0.115 / approved P11 dependency layout."""
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Request, Response
from fastapi.dependencies.utils import get_dependant
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from .service import AuthError


class PrivateRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe(request):
            try:
                # Bound JSON before validation; never echo supplied secrets.
                if request.method in {'POST', 'PUT'}:
                    chunks, size = [], 0
                    async for chunk in request.stream():
                        size += len(chunk)
                        if size > 4096:
                            return JSONResponse({'error': {'code': 'REQUEST_TOO_LARGE'}}, status_code=413,
                                                headers={'Cache-Control': 'no-store'})
                        chunks.append(chunk)
                    request._body = b''.join(chunks)
                return await handler(request)
            except RequestValidationError:
                # Default Pydantic error includes rejected inputs, including secrets.
                return JSONResponse({'error': {'code': 'INVALID_REQUEST'}}, status_code=422,
                                    headers={'Cache-Control': 'no-store'})
        return safe


class Login(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(min_length=1, max_length=128)


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    current_password: SecretStr = Field(min_length=1, max_length=128)
    new_password: SecretStr = Field(min_length=15, max_length=128)


class UsernameChange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    current_password: SecretStr = Field(min_length=1, max_length=128)
    new_username: str = Field(pattern=r'^[A-Za-z0-9_.@-]{3,64}$')


def install_admin_auth(app, auth, *, allowed_origins):
    """Call AFTER HarpIA/controls installation and BEFORE serving any requests.

    Existing technical POST ingest keeps the original Basic AND service token.
    Every other consumer of that same P11 admin dependency becomes session-only.
    No route, business handler, Store or credential is replaced.
    """
    if getattr(app.state, 'admin_auth', None) or app.dependency_overrides:
        raise RuntimeError('Auth already installed or dependency overrides present')
    origins = frozenset(allowed_origins)
    if not origins:
        raise ValueError('Explicit frontend origins required')
    for origin in origins:
        url = urlsplit(origin)
        if (url.scheme not in ('https', 'http') or not url.netloc or url.username or url.password
                or url.path or url.query or url.fragment or '*' in origin
                or (url.scheme == 'http' and url.hostname not in ('127.0.0.1', 'localhost', '[::1]', '::1'))):
            raise ValueError('Use exact HTTPS origins; HTTP only on loopback')
    health = next((r for r in app.routes if isinstance(r, APIRoute) and r.path == '/api/v1/p11/health'), None)
    if not health or len(health.dependant.dependencies) != 1:
        raise RuntimeError('Approved P11 admin dependency required')
    old_admin = health.dependant.dependencies[0].call
    bearer = HTTPBearer(auto_error=False, scheme_name='HarpiSenseAdminSession')

    def request_token(request: Request, c: HTTPAuthorizationCredentials | None = Depends(bearer)):
        origin = request.headers.get('origin')
        if origin and origin not in origins:
            raise AuthError(403, 'ORIGIN_DENIED')
        if not c or c.scheme.lower() != 'bearer':
            raise AuthError(401, 'AUTH_REQUIRED')
        return c.credentials

    def require_admin(token=Depends(request_token)):
        return auth.current(token)['username']

    def replace(nodes, path):
        for i, node in enumerate(nodes):
            if node.call is old_admin:
                nodes[i] = get_dependant(path=path, call=require_admin, name=node.name, use_cache=node.use_cache)
            else:
                replace(node.dependencies, path)

    technical = '/api/v1/p11/ingest/{kind}'
    for route in app.routes:
        if isinstance(route, APIRoute):
            if route.path == technical and route.methods == {'POST'}:
                continue
            replace(route.dependant.dependencies, route.path_format)

    @app.exception_handler(AuthError)
    async def auth_error(request, exc):
        headers = {'Cache-Control': 'no-store'}
        if exc.status == 401:
            headers['WWW-Authenticate'] = 'Bearer'
        if exc.retry_after:
            headers['Retry-After'] = str(exc.retry_after)
        return JSONResponse({'error': {'code': exc.code}}, status_code=exc.status, headers=headers)

    def no_store(response: Response, request: Request):
        response.headers['Cache-Control'] = 'no-store'
        origin = request.headers.get('origin')
        if origin and origin not in origins:
            raise AuthError(403, 'ORIGIN_DENIED')

    router = APIRouter(prefix='/api/v1/admin-auth', route_class=PrivateRoute,
                       dependencies=[Depends(no_store)])

    @router.post('/login')
    def login(body: Login):
        return auth.login(body.username, body.password.get_secret_value())

    @router.get('/session')
    def session(token=Depends(request_token)):
        return auth.current(token)

    @router.post('/logout', status_code=204)
    def logout(token=Depends(request_token)):
        auth.logout(token)
        return Response(status_code=204, headers={'Cache-Control': 'no-store'})

    @router.put('/password')
    def password(body: PasswordChange, token=Depends(request_token)):
        auth.change(token, body.current_password.get_secret_value(), password=body.new_password.get_secret_value())
        return {'status': 'credentials_changed', 'login_required': True, 'sessions_revoked': 'all'}

    @router.put('/username')
    def username(body: UsernameChange, token=Depends(request_token)):
        auth.change(token, body.current_password.get_secret_value(), username=body.new_username)
        return {'status': 'credentials_changed', 'login_required': True, 'sessions_revoked': 'all'}

    app.include_router(router)
    app.state.admin_auth = auth
    app.state.require_admin_session = require_admin
    app.openapi_schema = None
    return require_admin
