"""Response contract for the existing MFA candidate, with no runtime auth changes."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Exact(BaseModel):
    model_config = ConfigDict(extra='forbid')


class AdminSession(Exact):
    access_token: str = Field(pattern=r'^[A-Za-z0-9_-]{43}$')
    token_type: Literal['Bearer']
    expires_at: datetime
    idle_timeout_seconds: Literal[1800]
    username: str
    mfa_enrollment_required: bool | None = None
    mfa_enrollment_available: bool | None = None


class MFAChallenge(Exact):
    challenge_token: str = Field(pattern=r'^[A-Za-z0-9_-]{43}$')
    next_step: Literal['login', 'enroll']
    expires_at: datetime


class EnrollmentDetails(Exact):
    manual_key: str
    provisioning_uri: str
    qr_svg: str
    expires_at: datetime


class EnrollmentComplete(AdminSession):
    recovery_codes: list[str] = Field(min_length=10, max_length=10)


class SessionState(Exact):
    authenticated: Literal[True]
    username: str
    expires_at: datetime
    idle_timeout_seconds: Literal[1800]
    mfa_available: Literal[True]
    mfa_enabled: bool
    mfa_enrollment_available: Literal[True]
    email_recovery_available: Literal[False]


class CredentialChange(Exact):
    status: Literal['credentials_changed']
    login_required: Literal[True]
    sessions_revoked: Literal['all']


class ErrorDetail(Exact):
    code: str


class AuthFailure(Exact):
    error: ErrorDetail


RESPONSES = {
    ('post', '/login'): ('AdminSession', 'MFAChallenge'),
    ('post', '/bootstrap'): ('MFAChallenge',),
    ('post', '/local-recovery'): ('MFAChallenge',),
    ('post', '/mfa/enrollment/authorize'): ('MFAChallenge',),
    ('post', '/mfa/enrollment/begin'): ('EnrollmentDetails',),
    ('post', '/mfa/enrollment/confirm'): ('EnrollmentComplete',),
    ('post', '/mfa/verify'): ('AdminSession',),
    ('post', '/mfa/recover'): ('MFAChallenge',),
    ('get', '/session'): ('SessionState',),
    ('put', '/password'): ('CredentialChange',),
    ('put', '/username'): ('CredentialChange',),
}
MODELS = (AdminSession, MFAChallenge, EnrollmentDetails, EnrollmentComplete,
          SessionState, CredentialChange, AuthFailure)


def install_http_contract(app):
    """Describe actual response unions instead of FastAPI's untyped objects.

    No new route, account mechanism or response serialization. Network tests
    validate this published schema against the real JSON responses.
    """
    original = app.openapi

    def openapi():
        schema = original()
        components = schema.setdefault('components', {}).setdefault('schemas', {})
        for model in MODELS:
            definition = model.model_json_schema(ref_template='#/components/schemas/{model}')
            components.update(definition.pop('$defs', {}))
            components[model.__name__] = definition
        prefix = '/api/v1/admin-auth'
        for (method, path), models in RESPONSES.items():
            operation = schema['paths'][prefix+path][method]
            refs = [{'$ref': '#/components/schemas/'+name} for name in models]
            response = refs[0] if len(refs) == 1 else {'oneOf': refs}
            operation['responses']['200'] = {'description': 'Candidate response; partial challenge is not an admin session',
                'content': {'application/json': {'schema': response}}}
        for path, methods in schema['paths'].items():
            if not path.startswith(prefix):
                continue
            for operation in methods.values():
                if not isinstance(operation, dict) or 'responses' not in operation:
                    continue
                for status in (401, 403, 409, 413, 422, 429, 503):
                    operation['responses'][str(status)] = {'description': 'Sanitized authentication error',
                        'headers': {'Cache-Control': {'schema': {'const': 'no-store'}}},
                        'content': {'application/json': {'schema': {'$ref': '#/components/schemas/AuthFailure'}}}}
        schema['info']['description'] = ('MFA candidate, not an operational deployment or integration approval. '
            'Use only full access_token as administrative Bearer; challenges have limited purpose.')
        app.openapi_schema = schema
        return schema

    app.openapi = openapi
    app.openapi_schema = None
