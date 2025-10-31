from collections.abc import Mapping, Sequence
from typing import Any,  cast
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_422_UNPROCESSABLE_CONTENT,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from app.core.logging import get_logger


class ErrorBody(BaseModel):
    """Structured error body."""
    type: str
    message: str
    details: dict[str, object] | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody
    meta: dict[str, object]


def _build_meta(request: Request) -> dict[str, object]:
    """Collect metadata for error responses."""
    return {
        "request_id": getattr(request.state, "correlation_id", "-"),
        "tenant": getattr(request.state, "tenant", "-"),
        "path": request.url.path,
        "method": request.method,
    }

def _serialize_validation_errors(errors: Sequence[Mapping[Any, Any]]) -> list[dict[str, object]]:
    """Serialize validation errors, handling non-serializable objects in context."""

    serialized_errors: list[dict[str, object]] = []

    for error in errors:
        serialized_error: dict[str, object] = dict(error)

        if "ctx" in serialized_error and isinstance(serialized_error["ctx"], dict):
            ctx: dict[str, object] = cast(dict[str, object], serialized_error["ctx"]).copy()

            if "error" in ctx:
                error_value = ctx["error"]

                if hasattr(error_value, "__str__"):
                    ctx["error"] = str(error_value)
            serialized_error["ctx"] = ctx
        serialized_errors.append(serialized_error)
    return serialized_errors


def register_exception_handlers(app: FastAPI) -> None:
    """Register centralized exception."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        logger = get_logger(__name__, request)
        logger.warning("HTTP error", extra={"status_code": exc.status_code})
        # Handle complex detail objects (like shortages)
        if isinstance(exc.detail, dict):
            message = str(exc.detail) if len(str(exc.detail)) < 200 else "Request failed"
            details = exc.detail
        else:
            message = exc.detail or "HTTP error"
            details = None

        body = ErrorEnvelope(
            error=ErrorBody(type="http_error", message=message, details=details),
            meta=_build_meta(request),
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger = get_logger(__name__, request)
        logger.info("Validation error")
        body = ErrorEnvelope(
            error=ErrorBody(
                type="validation_error",
                message="Invalid request payload",
                details={"errors": _serialize_validation_errors(exc.errors())},
            ),
            meta=_build_meta(request),
        )
        return JSONResponse(
            status_code=HTTP_422_UNPROCESSABLE_CONTENT, content=body.model_dump()
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
        logger = get_logger(__name__, request)
        logger.warning("Database integrity error", extra={"error": str(exc)})

        # Extract meaningful error message
        error_message = str(exc.orig) if hasattr(exc, 'orig') and exc.orig else str(exc)

        # Check for specific constraint violations
        if "foreign key constraint" in error_message.lower():
            message = "Referenced resource not found"
            error_type = "reference_not_found"
        elif "unique constraint" in error_message.lower():
            message = "Resource already exists"
            error_type = "duplicate_resource"
        elif "check constraint" in error_message.lower():
            message = "Invalid data value"
            error_type = "invalid_value"
        else:
            message = "Data integrity violation"
            error_type = "integrity_error"

        body = ErrorEnvelope(
            error=ErrorBody(type=error_type, message=message),
            meta=_build_meta(request),
        )
        return JSONResponse(
            status_code=HTTP_400_BAD_REQUEST, content=body.model_dump()
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger = get_logger(__name__, request)
        logger.exception("Unhandled server error", exc_info=exc)
        body = ErrorEnvelope(
            error=ErrorBody(type="server_error", message="Internal Server Error"),
            meta=_build_meta(request),
        )
        return JSONResponse(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR, content=body.model_dump()
        )
