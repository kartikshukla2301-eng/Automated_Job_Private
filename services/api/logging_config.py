"""Structured JSON logging with request correlation and secret redaction."""

import json
import logging
import re
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Optional

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# Context variable tracking current request ID
request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

# Sensitive keys and patterns to redact from logs
SENSITIVE_KEYS = {
    "password",
    "token",
    "secret",
    "key",
    "api_key",
    "authorization",
    "cookie",
    "credential",
    "auth",
}

SENSITIVE_PATTERNS = [
    re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]+", re.IGNORECASE),
    re.compile(r"(api[_-]?key\s*[:=]\s*)[^\s,]+", re.IGNORECASE),
    re.compile(r"(password\s*[:=]\s*)[^\s,]+", re.IGNORECASE),
    re.compile(r"(token\s*[:=]\s*)[^\s,]+", re.IGNORECASE),
    re.compile(r"(secret\s*[:=]\s*)[^\s,]+", re.IGNORECASE),
]

REQUEST_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")


def redact_sensitive_data(val: Any) -> Any:
    """Recursively scrub sensitive keys and token patterns from objects."""
    if isinstance(val, dict):
        return {
            k: ("[REDACTED]" if any(s in k.lower() for s in SENSITIVE_KEYS) else redact_sensitive_data(v))
            for k, v in val.items()
        }
    elif isinstance(val, (list, tuple)):
        return [redact_sensitive_data(item) for item in val]
    elif isinstance(val, str):
        redacted = val
        for pattern in SENSITIVE_PATTERNS:
            redacted = pattern.sub(r"\1[REDACTED]", redacted)
        return redacted
    return val


class RedactionFilter(logging.Filter):
    """Logging filter ensuring log messages and arguments are sanitized."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_sensitive_data(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = redact_sensitive_data(record.args)
            elif isinstance(record.args, (list, tuple)):
                record.args = tuple(redact_sensitive_data(arg) for arg in record.args)
        return True


class JSONFormatter(logging.Formatter):
    """Formatter outputting standardized, single-line JSON logs."""

    def __init__(self, service_name: str = "job-agent-api") -> None:
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        # Standard timestamp in UTC ISO-8601
        log_payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_ctx.get(),
        }

        # Include custom extra attributes passed to logger calls
        reserved_attrs = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "message",
        }
        extras = {
            k: redact_sensitive_data(v)
            for k, v in record.__dict__.items()
            if k not in reserved_attrs and not k.startswith("_")
        }
        if extras:
            log_payload["extra"] = extras

        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_payload)


def setup_logging(
    service_name: str = "job-agent-api",
    log_level: str = "INFO",
) -> logging.Logger:
    """Initialize structured logging once without duplicate handlers."""
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear existing handlers to prevent duplicates on repeated setup
    logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter(service_name=service_name))
    handler.addFilter(RedactionFilter())
    logger.addHandler(handler)

    return logger


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    """Middleware enforcing valid request IDs and emitting structured request logs."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        raw_request_id = request.headers.get("X-Request-ID")
        # Strict validation: alphanumeric + hyphens/underscores, max 64 chars
        if raw_request_id and REQUEST_ID_REGEX.match(raw_request_id):
            request_id = raw_request_id
        else:
            request_id = uuid.uuid4().hex

        token = request_id_ctx.set(request_id)
        logger = logging.getLogger("services.api.http")
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            response.headers["X-Request-ID"] = request_id

            logger.info(
                "HTTP request completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            return response
        except Exception:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.exception(
                "HTTP request failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                },
            )
            raise
        finally:
            request_id_ctx.reset(token)
