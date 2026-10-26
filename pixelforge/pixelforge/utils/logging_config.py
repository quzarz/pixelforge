"""Centralised logging with secret redaction. Never logs images or generated code."""

from __future__ import annotations

import logging

from pixelforge.utils.errors import redact_secrets

_LOGGER_NAME = "pixelforge"
_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


class RedactingFilter(logging.Filter):
    """Mask API-key-like strings in every record, including exception text."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_secrets(record.getMessage())
        record.args = None
        if record.exc_info:
            record.exc_text = redact_secrets(logging.Formatter().formatException(record.exc_info))
            record.exc_info = None
        return True


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure the ``pixelforge`` logger once (idempotent) and return it."""
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    if not any(isinstance(f, RedactingFilter) for h in logger.handlers for f in h.filters):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_FORMAT))
        handler.addFilter(RedactingFilter())
        logger.addHandler(handler)
        logger.propagate = False
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child logger of the ``pixelforge`` logger."""
    return logging.getLogger(f"{_LOGGER_NAME}.{name}")
