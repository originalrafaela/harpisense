"""Reuse the existing Basic dependency and operational settings URL contract."""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from .controls import Rejected


class Change(BaseModel):
    model_config = ConfigDict(extra='forbid')
    value: dict
    expected_revision: StrictInt = Field(ge=1)
    reason: str = Field(min_length=3, max_length=1000, pattern=r'\S')


class Stop(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: str = Field(min_length=3, max_length=1000, pattern=r'\S')


def install_controls(app, controls):
    health = next((r for r in app.routes if isinstance(r, APIRoute) and r.path == '/api/v1/p11/health'), None)
    if not health or len(health.dependant.dependencies) != 1:
        raise RuntimeError('Authenticated P11 health dependency required')
    admin = health.dependant.dependencies[0].call
    router = APIRouter(prefix='/api/v1/security')

    def invoke(fn, **kwargs):
        try:
            return fn(**kwargs)
        except Rejected as exc:
            raise HTTPException(exc.status, exc.detail) from exc
        except ValueError as exc:
            raise HTTPException(422, 'Contrato de controles inválido') from exc
        except Exception as exc:
            raise HTTPException(503, 'Persistência/coordenação operacional indisponível; alteração não confirmada.') from exc

    @router.get('/settings/mode/default')
    def read(actor=Depends(admin)):
        return invoke(controls.get)

    @router.put('/settings/mode/default')
    def change(body: Change, actor=Depends(admin)):
        return invoke(controls.change, **body.model_dump(), actor=actor)

    @router.post('/emergency-stop')
    def stop(body: Stop, actor=Depends(admin)):
        return invoke(controls.stop, reason=body.reason, actor=actor)

    @router.get('/audit')
    def audit(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), actor=Depends(admin)):
        return invoke(controls.repository.audit, limit=limit, offset=offset)

    original = health.dependant.call

    def capabilities(**kwargs):
        value = original(**kwargs)
        try:
            state = controls.get()
            value['operational_controls'] = {**state['value'], 'revision': state['revision'],
                  'emergency_stopped': state['emergency_stopped'], 'updated_at': state['updated_at'],
                  'real_execution_blocked': True}
        except Exception:
            value['operational_controls'] = {'status': 'unavailable', 'real_execution_blocked': True}
        value['control_api'] = {'version': 1, 'settings': '/api/v1/security/settings/mode/default',
                                'audit': '/api/v1/security/audit', 'real_execution_blocked': True}
        return value

    health.dependant.call = capabilities
    app.include_router(router)
