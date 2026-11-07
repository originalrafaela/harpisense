"""Install after the existing session authentication; never expose inference."""
import psycopg
from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse

from admin_auth.api import PrivateRoute
from .store import Missing, XAIStore
from .schemas import MODELS


def install_xai_api(app, store, *, installation_id=None, asset_identifier_column='technical_id'):
    if getattr(app.state, 'xai_reader', None):
        raise RuntimeError('XAI reader already installed')
    reader = XAIStore(store._connect, installation_id, asset_identifier_column)

    def private(response: Response):
        response.headers['Cache-Control'] = 'no-store'

    router = APIRouter(prefix='/api/v1/p11', route_class=PrivateRoute,
        dependencies=[Depends(app.state.require_admin_session), Depends(private)])

    def invoke(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Missing as exc:
            return JSONResponse({'error':{'code':str(exc)}}, status_code=404, headers={'Cache-Control':'no-store'})
        except (psycopg.Error, ValueError, KeyError, TypeError):
            return JSONResponse({'error':{'code':'XAI_UNAVAILABLE'}}, status_code=503, headers={'Cache-Control':'no-store'})

    @router.get('/detections/{detection_id}/explanations')
    def detection(detection_id: str, incident_id: str | None = Query(None, min_length=1, max_length=256),
                  incident_revision: int | None = Query(None, ge=1)):
        if incident_revision is not None and incident_id is None:
            return JSONResponse({'error':{'code':'INCIDENT_ID_REQUIRED'}},status_code=422,headers={'Cache-Control':'no-store'})
        return invoke(reader.detection, detection_id, incident_id=incident_id, incident_revision=incident_revision)

    @router.get('/incidents/{incident_id}/explanations')
    def incident(incident_id: str, incident_revision: int | None = Query(None, ge=1)):
        return invoke(reader.incident, incident_id, incident_revision)

    @router.get('/observations/{collection_session_id}/{window_id}/explanations')
    def observation(collection_session_id: str, window_id: str,
                    sensor_id: str | None = Query(None, min_length=1, max_length=256)):
        return invoke(reader.observation, collection_session_id, window_id, sensor_id)

    app.include_router(router)
    app.state.xai_reader = reader
    original = app.openapi

    def openapi():
        schema = original()
        schema.setdefault('components',{}).setdefault('schemas',{}).update(MODELS)
        paths = {
            '/api/v1/p11/detections/{detection_id}/explanations':'XAIAnalysis',
            '/api/v1/p11/incidents/{incident_id}/explanations':'XAIIncident',
            '/api/v1/p11/observations/{collection_session_id}/{window_id}/explanations':'XAIObservation'}
        for path,model in paths.items():
            schema['paths'][path]['get']['responses']['200']={'description':'Persisted XAI only; no inference or action',
                'content':{'application/json':{'schema':{'$ref':'#/components/schemas/'+model}}}}
        app.openapi_schema = schema
        return schema

    app.openapi = openapi
    app.openapi_schema = None
    return reader
