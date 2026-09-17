import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.core.config import settings

security = HTTPBasic(auto_error=False)


def _reject_missing_credentials() -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing HTTP Basic credentials",
        headers={"WWW-Authenticate": "Basic"},
    )


def _reject_invalid_credentials(realm: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=f"Invalid {realm} credentials",
        headers={"WWW-Authenticate": "Basic"},
    )


def _configured_secret(value: str | None) -> bool:
    return bool(value and value.strip())


def require_admin(credentials: Annotated[HTTPBasicCredentials | None, Depends(security)]) -> str:
    if not _configured_secret(settings.admin_password):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin password is not configured",
        )
    if credentials is None:
        _reject_missing_credentials()

    username_ok = secrets.compare_digest(credentials.username, settings.admin_username)
    password_ok = secrets.compare_digest(credentials.password, settings.admin_password)
    if not (username_ok and password_ok):
        _reject_invalid_credentials("admin")
    return credentials.username


def require_gateway(credentials: Annotated[HTTPBasicCredentials | None, Depends(security)]) -> str:
    if not _configured_secret(settings.gateway_username) or not _configured_secret(settings.gateway_password):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gateway credentials are not configured",
        )
    if _configured_secret(settings.admin_password) and secrets.compare_digest(
        settings.gateway_password or "",
        settings.admin_password or "",
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gateway password must be separate from admin password",
        )
    if credentials is None:
        _reject_missing_credentials()

    username_ok = secrets.compare_digest(credentials.username, settings.gateway_username or "")
    password_ok = secrets.compare_digest(credentials.password, settings.gateway_password or "")
    if not (username_ok and password_ok):
        _reject_invalid_credentials("gateway")
    return credentials.username
