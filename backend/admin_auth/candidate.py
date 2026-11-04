"""Isolated integration point; shared delivery/bootstrap is intentionally untouched."""
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from .api import PrivateRoute, install_admin_auth
from .mfa import MFAAdminAuth
from .service import AuthError


class Challenge(BaseModel):
    model_config = ConfigDict(extra='forbid')
    challenge_token: SecretStr = Field(min_length=43, max_length=43)


class Factor(Challenge):
    code: SecretStr = Field(min_length=6, max_length=32)


class Bootstrap(BaseModel):
    model_config = ConfigDict(extra='forbid')
    bootstrap_secret: SecretStr = Field(min_length=43, max_length=43)
    username: str = Field(pattern=r'^[A-Za-z0-9_.@-]{3,64}$')
    password: SecretStr = Field(min_length=8, max_length=128)


class EnrollmentAuthorization(BaseModel):
    model_config = ConfigDict(extra='forbid')
    current_password: SecretStr = Field(min_length=1, max_length=128)
    code: SecretStr | None = Field(default=None, min_length=6, max_length=6)


def install_candidate_admin_auth(app, conninfo, *, protection_key, allowed_origins, technical_credentials=()):
    """Call instead of install_admin_auth, AFTER P11/controls, BEFORE config API.

    Requires both explicit migrations. Does not run migrations or create accounts.
    Same existing auth HTTP paths and app.state hooks; no second auth layer.
    """
    auth = MFAAdminAuth(conninfo, protection_key=protection_key, technical_credentials=technical_credentials)
    origins = tuple(allowed_origins)
    install_admin_auth(app, auth, allowed_origins=origins)

    def private(response: Response, request: Request):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Pragma'] = 'no-cache'
        if request.headers.get('origin') and request.headers['origin'] not in origins:
            raise AuthError(403, 'ORIGIN_DENIED')

    router = APIRouter(prefix='/api/v1/admin-auth', route_class=PrivateRoute, dependencies=[Depends(private)])

    @router.post('/bootstrap')
    def bootstrap(body: Bootstrap):
        return auth.bootstrap(body.bootstrap_secret.get_secret_value(), body.username, body.password.get_secret_value())

    @router.post('/local-recovery')
    def local_recovery(body: Bootstrap):
        return auth.local_recover(body.bootstrap_secret.get_secret_value(), body.username, body.password.get_secret_value())

    @router.post('/mfa/enrollment/authorize')
    def authorize(body: EnrollmentAuthorization, token=Depends(app.state.require_admin_token)):
        return auth.authorize_enrollment(token, body.current_password.get_secret_value(),
                                         body.code.get_secret_value() if body.code else None)

    @router.post('/mfa/enrollment/begin')
    def begin(body: Challenge):
        return auth.begin_enrollment(body.challenge_token.get_secret_value())

    @router.post('/mfa/enrollment/confirm')
    def confirm(body: Factor):
        return auth.confirm_enrollment(body.challenge_token.get_secret_value(), body.code.get_secret_value())

    @router.post('/mfa/verify')
    def verify(body: Factor):
        return auth.verify_login(body.challenge_token.get_secret_value(), body.code.get_secret_value())

    @router.post('/mfa/recover')
    def recover(body: Factor):
        return auth.verify_login(body.challenge_token.get_secret_value(), body.code.get_secret_value(), recovery=True)

    @router.post('/mfa/cancel', status_code=204)
    def cancel(body: Challenge):
        auth.cancel_challenge(body.challenge_token.get_secret_value())
        return Response(status_code=204, headers={'Cache-Control': 'no-store'})

    app.include_router(router)
    return auth
