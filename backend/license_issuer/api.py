"""Dedicated issuer ASGI app; terminate HTTPS here or at a trusted TLS ingress.

Never mount into the local runtime. No forwarded header grants TLS or issuance.
"""
import hmac
from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, SecretStr, Field
from .envelopes import loads
from .service import IssuerError


class Exact(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Challenge(Exact):
    activation_key: SecretStr = Field(min_length=43,max_length=43)
    installation_id: str
    installation_public_key: str
    platform: str


class Activate(Exact):
    challenge: dict
    proof: dict


class Empty(Exact):
    pass


def create_issuer_app(issuer, *, distributor_token, require_https=True):
    if not distributor_token or len(distributor_token) < 32:
        raise ValueError('Distributor credential required')
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware('http')
    async def private(request, call_next):
        if require_https and request.url.scheme != 'https':
            return JSONResponse({'error':{'code':'HTTPS_REQUIRED','message':'HTTPS_REQUIRED'}},status_code=403,headers={'Cache-Control':'no-store'})
        if request.method == 'POST':
            chunks, size = [], 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > 16384:
                    return JSONResponse({'error':{'code':'INVALID_REQUEST','message':'INVALID_REQUEST'}},status_code=400,headers={'Cache-Control':'no-store'})
                chunks.append(chunk)
            request._body = b''.join(chunks)
            try:
                loads(request._body)
            except (ValueError, UnicodeError, TypeError):
                return JSONResponse({'error':{'code':'INVALID_REQUEST','message':'INVALID_REQUEST'}},status_code=400,headers={'Cache-Control':'no-store'})
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        return response

    from fastapi.exceptions import RequestValidationError

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse({'error':{'code':'INVALID_REQUEST','message':'INVALID_REQUEST'}},status_code=400,headers={'Cache-Control':'no-store'})

    @app.exception_handler(IssuerError)
    async def issuer_error(request, exc):
        headers = {'Cache-Control':'no-store'}
        if exc.status == 429:
            headers['Retry-After'] = '60'
        return JSONResponse({'error':{'code':exc.code,'message':exc.message}},status_code=exc.status,headers=headers)

    def distributor(request: Request):
        supplied = request.headers.get('authorization', '')
        if not hmac.compare_digest(supplied.encode(), ('Bearer '+distributor_token).encode()):
            raise IssuerError(401, 'DISTRIBUTOR_AUTH_REQUIRED')

    @app.post('/api/v1/licenses/issue', dependencies=[Depends(distributor)])
    def issue(body: Empty):
        return issuer.issue()

    @app.post('/api/v1/licenses/challenges')
    def challenges(body: Challenge):
        return issuer.challenge(body.activation_key.get_secret_value(), body.installation_id, body.installation_public_key, body.platform)

    @app.post('/api/v1/licenses/activate')
    def activate(body: Activate):
        return issuer.activate(body.challenge, body.proof)

    return app
