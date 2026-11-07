"""Session-only HTTP composition for the existing internal action-review hook."""
from datetime import datetime, timezone
import re

import psycopg
from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from admin_auth.api import PrivateRoute
from .action_bridge import PersistentActionResolver, ProjectionRepository
from .control_store import PostgresControls
from .controls import Controls, Rejected
from .operational_queue import OperationalQueue


class ActionRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    incident_revision:StrictInt=Field(ge=1)
    decision_revision:StrictInt=Field(ge=1)
    expected_revision:StrictInt=Field(ge=1)


class SpecificApproval(ActionRequest):
    expected_action:str=Field(pattern=r'^[a-f0-9]{64}$')


def install_action_api(app,store):
    def private(response:Response):response.headers['Cache-Control']='no-store'
    router=APIRouter(prefix='/api/v1/p11',route_class=PrivateRoute,
        dependencies=[Depends(app.state.require_admin_session),Depends(private)])

    def invoke(operation,incident_id,decision_id,body,actor):
        try:
            from .action_review import ActionReview
            controls=Controls(ProjectionRepository(PostgresControls(store.conninfo)),OperationalQueue())
            resolver=PersistentActionResolver(incident_id=incident_id,
                incident_revision=body.incident_revision,decision_revision=body.decision_revision)
            service=ActionReview(controls,resolver)
            arguments={'expected_revision':body.expected_revision,'actor':actor,
                       'now':datetime.now(timezone.utc).isoformat()}
            if operation=='approve':arguments['expected_action']=body.expected_action
            return getattr(service,operation)(decision_id,**arguments)
        except ImportError:
            return JSONResponse({'error':{'code':'ACTION_MODULE_NOT_INTEGRATED'}},503,headers={'Cache-Control':'no-store'})
        except Rejected as exc:
            return JSONResponse({'error':exc.detail},exc.status,headers={'Cache-Control':'no-store'})
        except ValueError as exc:
            code=str(exc) if re.fullmatch(r'[A-Z_]{3,100}',str(exc)) else 'ACTION_REVALIDATION_FAILED'
            return JSONResponse({'error':{'code':code,'defense_dispatched':False}},409,headers={'Cache-Control':'no-store'})
        except (psycopg.Error,KeyError,TypeError):
            return JSONResponse({'error':{'code':'ACTION_DATA_UNAVAILABLE','defense_dispatched':False}},503,
                                headers={'Cache-Control':'no-store'})

    @router.post('/incidents/{incident_id}/actions/{decision_id}/approval')
    def approve(incident_id:str,decision_id:str,body:SpecificApproval,actor=Depends(app.state.require_admin_session)):
        return invoke('approve',incident_id,decision_id,body,actor)

    @router.post('/incidents/{incident_id}/actions/{decision_id}/simulate')
    def simulate(incident_id:str,decision_id:str,body:ActionRequest,actor=Depends(app.state.require_admin_session)):
        return invoke('simulate',incident_id,decision_id,body,actor)

    app.include_router(router)
