"""Structured JSON logging with request/task correlation.

One JSON object per line on stdout, from both Flask and Celery. A request_id
generated per HTTP request is propagated into Celery task headers, so a single
id links a web request to the background work it triggered.

Enabled by LOG_FORMAT=json (the default); set LOG_FORMAT=text for readable
local output.
"""
import json
import logging
import os
import sys
import uuid
from contextvars import ContextVar

# ContextVar rather than flask.g: the same id must be readable from Celery
# tasks and worker threads, which have no request context.
_request_id: ContextVar[str] = ContextVar("request_id", default="-")

REQUEST_ID_HEADER = "X-Request-ID"


def set_request_id(value: str | None = None) -> str:
    rid = value or uuid.uuid4().hex[:16]
    _request_id.set(rid)
    return rid


def get_request_id() -> str:
    return _request_id.get()


class JsonFormatter(logging.Formatter):
    """Render each record as a single-line JSON object."""

    # Attributes LogRecord always carries; anything else is caller-supplied
    # and worth emitting.
    _STANDARD = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
        "asctime", "message", "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None) or get_request_id(),
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        for key, value in record.__dict__.items():
            if key not in self._STANDARD and key not in payload:
                try:
                    json.dumps(value)
                    payload[key] = value
                except (TypeError, ValueError):
                    payload[key] = repr(value)

        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    """Install the root handler. Safe to call more than once."""
    level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    use_json = os.getenv("LOG_FORMAT", "json").lower() == "json"

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter()
        if use_json
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s [%(request_id)s]: %(message)s")
    )

    root = logging.getLogger()
    for existing in root.handlers[:]:
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)


def init_app(app) -> None:
    """Assign a request id per request and echo it back to the caller."""

    @app.before_request
    def _assign_request_id():
        from flask import request
        set_request_id(request.headers.get(REQUEST_ID_HEADER))

    @app.after_request
    def _return_request_id(response):
        response.headers[REQUEST_ID_HEADER] = get_request_id()
        return response
