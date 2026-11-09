"""Current integration entry point for the existing, already provisioned gateway.

No bootstrap, migrations, synthetic data or technical credential rotation on start.
"""
import json
import os
from pathlib import Path
import sys

RELEASE = Path(__file__).resolve().parent
sys.path[:0] = [str(RELEASE/p) for p in ('backend', 'backend/domain', 'genai')]


def build_app(settings=None):
    from delivery.app import build_candidate_app
    from config_manager.schema import Capabilities
    settings = settings or json.loads((RELEASE/'settings.json').read_text())
    base = Path(settings['base'])
    # Existing service configuration stays local and is never copied into release metadata.
    env = dict(line.split('=', 1) for line in (base/'.env').read_text().splitlines()
               if '=' in line and not line.startswith('#'))
    os.environ.update(env)
    os.environ['DATABASE_URL'] = settings.get('rehearsal_dsn', env['HARPISENSE_DATABASE_URL'])
    os.environ['HARPISENSE_BITNET_ENABLED'] = '1' if settings.get('bitnet_enabled') else '0'
    if settings.get('bitnet_url'):
        os.environ['HARPIA_URL'] = settings['bitnet_url']
    mqtt = base/'.mqtt_password'
    credentials = [(env['HARPISENSE_ADMIN_USER'], env['HARPISENSE_ADMIN_PASSWORD'])]
    if mqtt.exists():
        credentials.append(('harpisense_mqtt', mqtt.read_text().strip()))
    return build_candidate_app(installation_id=settings['installation_id'],
        capabilities=Capabilities(revision=settings['capability_revision']),
        allowed_origins=settings['allowed_origins'], technical_credentials=credentials,
        protection_key=Path(settings['key_file']).read_bytes().strip(),
        presentation_directory=settings['presentation_directory'])


def build_web_app(settings=None):
    """Keep direct service API and serve the built panel on the same loopback port."""
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from fastapi.staticfiles import StaticFiles
    api = build_app(settings)
    web = FastAPI(docs_url=None, redoc_url=None)
    web.include_router(api.router)

    @web.middleware('http')
    async def browser_transport(request: Request, call_next):
        if request.url.path.startswith('/p11-api/'):
            authorization = request.headers.get('authorization', '')
            if '/ingest/' in request.url.path:
                return JSONResponse({'error': {'code': 'NOT_FOUND'}}, status_code=404)
            if authorization and not authorization.startswith('Bearer '):
                return JSONResponse({'error': {'code': 'AUTH_REQUIRED'}}, status_code=401)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    web.mount('/p11-api', api)
    web.mount('/', StaticFiles(directory=str(RELEASE/'frontend/dist'), html=True))
    return web


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(build_web_app(), host='127.0.0.1', port=8000, access_log=False)
