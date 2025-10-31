import logging
import sys
from typing import Final
from collections.abc import Mapping
from logging import LoggerAdapter, LogRecord
from typing_extensions import override
from fastapi import Request

_LOG_FORMAT: Final[str] = (
    "%(asctime)s %(levelname)s %(name)s :: %(message)s "
    "[req=%(request_id)s tenant=%(tenant)s]"
)


class RequestLogFilter(logging.Filter):
    """
    Ensures every record has request_id and tenant keys.
    """

    @override
    def filter(self, record: LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        if not hasattr(record, "tenant"):
            record.tenant = "-"
        return True


def setup_logging(level: int = logging.INFO) -> None:
    """
    Configure root/uvicorn loggers (request_id/tenant).
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.addFilter(RequestLogFilter())
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(handler)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.setLevel(level)
        lg.addHandler(handler)

def get_logger(
    name: str,
    request: Request | None = None
) -> LoggerAdapter[logging.Logger]:
    """
    Attach request context (request_id, tenant).
    Usage: logger = get_logger(__name__, request)
    """
    extra: Mapping[str, str] = {}
    if request is not None:
        extra["request_id"] = getattr(request.state, "correlation_id", "-")
        extra["tenant"] = getattr(request.state, "tenant", "-")
    return LoggerAdapter(logging.getLogger(name), extra)
