from collections.abc import Awaitable
from typing import Callable
from fastapi import Response
from typing_extensions import override
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND
)
from app.db.session import engine


def _schema_exists(tenant: str) -> bool:
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :s"),
            {"s": tenant},
        ).first()
        return bool(result)


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Reads X-Tenant header.
    - 400 if missing
    - 404 if schema not found
    - Sets `request.state.tenant`
    - Sets search_path to `<tenant>, public`
    """

    def __init__(self, app: ASGIApp, header_name: str = "X-Tenant"):
        super().__init__(app)
        self.header_name: str = header_name

    @override
    async def dispatch(
          self,
          request: Request,
          call_next: Callable[[Request], Awaitable[Response]],
      ) -> Response:
        # Skip tenant validation
        if request.url.path in ["/", "/docs", "/redoc", "/openapi.json", "/api/v1/openapi.json"]:
            request.state.tenant = "default"
            response = await call_next(request)
            return response

        if "/bootstrap" in request.url.path:
            # Extract tenant from URL path /api/v1/tenants/{tenant}/bootstrap
            path_parts = request.url.path.strip("/").split("/")
            if len(path_parts) >= 4 and path_parts[0] == "api" and path_parts[1] == "v1" and path_parts[2] == "tenants":
                tenant = path_parts[3]
                # Allow alphanumeric, hyphens, and underscores (common in tenant names)
                import re
                if not re.match(r'^[a-zA-Z0-9_-]+$', tenant):
                    return JSONResponse(
                        status_code=HTTP_400_BAD_REQUEST,
                        content={
                            "error": {
                                "type": "validation_error",
                                "message": "Invalid tenant name",
                            },
                            "meta": {
                                "request_id": getattr(request.state, "correlation_id", "-"),
                                "tenant": tenant,
                            },
                        },
                    )
                if not tenant or len(tenant) > 63:
                    return JSONResponse(
                        status_code=HTTP_400_BAD_REQUEST,
                        content={
                            "error": {
                                "type": "validation_error",
                                "message": "Tenant name must be 1-63 characters",
                            },
                            "meta": {
                                "request_id": getattr(request.state, "correlation_id", "-"),
                                "tenant": tenant,
                            },
                        },
                    )
                # Set tenant from URL and proceed
                request.state.tenant = tenant
                response = await call_next(request)
                return response

        tenant = request.headers.get(self.header_name)

        if not tenant:
            return JSONResponse(
                status_code=HTTP_400_BAD_REQUEST,
                content={
                    "error": {
                        "type": "missing_tenant",
                        "message": "X-Tenant header is required",
                    },
                    "meta": {
                        "request_id": getattr(request.state, "correlation_id", "-"),
                        "tenant": "-",
                    },
                },
            )
        elif not _schema_exists(tenant):
            return JSONResponse(
                status_code=HTTP_404_NOT_FOUND,
                content={
                    "error": {
                        "type": "tenant_not_found",
                        "message": f"Tenant schema '{tenant}' not found",
                    },
                    "meta": {
                        "request_id": getattr(request.state, "correlation_id", "-"),
                        "tenant": tenant,
                    },
                },
            )

        try:
            with engine.connect() as conn:
                _ = conn.execute(text(f'SET search_path TO "{tenant}", public'))
        except SQLAlchemyError:
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "type": "tenant_context_error",
                        "message": "Failed to set tenant search_path",
                    },
                    "meta": {
                        "request_id": getattr(request.state, "correlation_id", "-"),
                        "tenant": tenant,
                    },
                },
            )

        request.state.tenant = tenant

        response = await call_next(request)
        response.headers[self.header_name] = tenant
        return response
