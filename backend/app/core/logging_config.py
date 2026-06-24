"""structlog → JSON logging. Routes stdlib `wedfind.*` + uvicorn loggers through
a structlog formatter so every existing logger.info(...) call gains the
timestamp/level/logger/request_id fields. Toggle with LOG_JSON.
"""
import logging
import sys

import structlog

from ..config import settings
from .request_id import get_request_id


def _add_request_id(logger, method_name, event_dict):
    rid = get_request_id()
    if rid:
        event_dict["request_id"] = rid
    return event_dict


_SHARED = [
    structlog.contextvars.merge_contextvars,
    _add_request_id,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
]


def configure_logging() -> None:
    structlog.configure(
        processors=_SHARED + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    renderer = (
        structlog.processors.JSONRenderer() if settings.LOG_JSON
        else structlog.dev.ConsoleRenderer()
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=_SHARED,
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    logging.getLogger("wedfind").setLevel(logging.INFO)
