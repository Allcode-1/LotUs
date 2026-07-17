import json
import logging
import sys
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Any


request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

LOG_RECORD_RESERVED_FIELDS = set(
    logging.LogRecord(
        name="",
        level=0,
        pathname="",
        lineno=0,
        msg="",
        args=(),
        exc_info=None,
    ).__dict__
) | {
    "asctime",
    "message",
    "metadata_suffix",
}


def set_request_id(request_id: str) -> Token[str]:
    return request_id_var.set(request_id)


def reset_request_id(token: Token[str]) -> None:
    request_id_var.reset(token)


def get_request_id() -> str:
    return request_id_var.get()


def normalize_log_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    return str(value)


def get_log_metadata(record: logging.LogRecord) -> dict[str, Any]:
    metadata = {}
    for key, value in record.__dict__.items():
        if key in LOG_RECORD_RESERVED_FIELDS or key.startswith("_"):
            continue
        metadata[key] = normalize_log_value(value)
    return metadata


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class PlainLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "request_id"):
            record.request_id = get_request_id()

        metadata = get_log_metadata(record)
        metadata.pop("request_id", None)
        if metadata:
            record.metadata_suffix = " | " + " ".join(
                f"{key}={json.dumps(value, default=str)}"
                for key, value in sorted(metadata.items())
            )
        else:
            record.metadata_suffix = ""

        return super().format(record)


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", get_request_id()),
        }
        payload.update(get_log_metadata(record))

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, ensure_ascii=False)


def get_log_level(log_level: str) -> int:
    level = getattr(logging, log_level.upper(), None)
    if isinstance(level, int):
        return level

    return logging.INFO


def build_formatter(log_format: str) -> logging.Formatter:
    if log_format.lower() == "json":
        return JsonLogFormatter()

    return PlainLogFormatter(
        fmt=(
            "%(asctime)s | %(levelname)-8s | %(name)s | "
            "req=%(request_id)s | %(message)s%(metadata_suffix)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def configure_logging(log_level: str = "INFO", log_format: str = "plain") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(build_formatter(log_format))

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(get_log_level(log_level))
