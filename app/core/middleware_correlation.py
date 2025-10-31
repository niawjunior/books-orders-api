from typing_extensions import override
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from starlette.requests import Request
from starlette.responses import Response
from typing import Callable
from collections.abc import Awaitable

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, header_name: str = "X-Request-ID"):
        super().__init__(app)
        self.header_name: str = header_name

    @override
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]]
    ):
        corr_id = request.headers.get(self.header_name) or str(uuid.uuid4())
        request.state.correlation_id = corr_id
        response = await call_next(request)
        response.headers[self.header_name] = corr_id
        return response
