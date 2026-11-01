"""
Structured logging configuration.
Dev: pretty console output. Production: JSON lines for log aggregation.
Request-scoped fields (request_id, path, ...) are bound via structlog contextvars
in the middleware in main.py.
"""

import logging
import sys

import structlog

from app.core.config import settings


def configure_logging() -> None:
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    # JSON everywhere that ships logs to an aggregator — which is every
    # deployed environment, not just production.
    if settings.is_internet_facing:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if settings.DEBUG else logging.INFO
        ),
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )
