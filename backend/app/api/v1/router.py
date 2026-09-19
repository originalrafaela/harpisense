from fastapi import APIRouter

from app.api.v1.routes import health, ingest, network_events, telemetry

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
api_router.include_router(telemetry.router, prefix="/telemetry", tags=["telemetry"])
api_router.include_router(network_events.router, prefix="/network-events", tags=["network-events"])
