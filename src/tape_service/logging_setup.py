import json
import logging
import re
import sys
from logging import LogRecord
from typing import Any

_SECRET_KEYS = re.compile(r"(token|secret|password|cookie|authorization|session_hash)", re.I)

_STD_ATTRS = frozenset(
    {
        "args",
        "msg",
        "levelname",
        "name",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "pathname",
        "filename",
        "module",
        "levelno",
        "taskName",
    }
)


class JsonFormatter(logging.Formatter):
    def format(self, record: LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for k, v in record.__dict__.items():
            if k in _STD_ATTRS:
                continue
            payload[k] = _redact(k, v)
        return json.dumps(payload, default=str, ensure_ascii=False)


def _redact(key: str, value: Any) -> Any:
    if _SECRET_KEYS.search(key):
        return "***REDACTED***"
    return value


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    for name in ("uvicorn.access",):
        logging.getLogger(name).propagate = False
