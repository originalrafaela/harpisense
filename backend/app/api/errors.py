from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.services.idempotency import IdentifierConflictError


def error_response(status_code: int, code: str, message: str, details: list | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder({"error": {"code": code, "message": message, "details": details or []}}),
    )


def _http_error_code(status_code: int) -> str:
    if status_code == status.HTTP_401_UNAUTHORIZED:
        return "authentication_error"
    if status_code == status.HTTP_403_FORBIDDEN:
        return "authorization_error"
    if status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
        return "configuration_error"
    return "http_error"


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "HTTP error"
    response = error_response(exc.status_code, _http_error_code(exc.status_code), message)
    for name, value in (exc.headers or {}).items():
        response.headers[name] = value
    return response


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "validation_error",
        "Invalid payload",
        exc.errors(),
    )


async def identifier_conflict_handler(request: Request, exc: IdentifierConflictError) -> JSONResponse:
    return error_response(
        status.HTTP_409_CONFLICT,
        "identifier_conflict",
        f"{exc.identifier_name} already exists with different content",
        [{"field": exc.identifier_name}],
    )


async def database_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    return error_response(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "database_error",
        "Database operation failed",
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(IdentifierConflictError, identifier_conflict_handler)
    app.add_exception_handler(SQLAlchemyError, database_exception_handler)
