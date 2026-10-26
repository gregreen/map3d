"""Logging configuration: one stream handler, key=value event records.

Container logs are collected by the platform (CloudWatch on AWS), so we write
to stdout and let the log driver handle rotation and shipping.
"""

from __future__ import annotations

import logging
import sys

_CONFIGURED = False


def configure_logging(level: str = "INFO") -> None:
    global _CONFIGURED

    root = logging.getLogger()
    root.setLevel(level.upper())

    if _CONFIGURED:
        for handler in root.handlers:
            handler.setLevel(level.upper())
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level.upper())
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    root.addHandler(handler)

    # gunicorn's error log would otherwise duplicate ours on stderr.
    logging.getLogger("gunicorn.error").handlers = []
    logging.getLogger("gunicorn.error").propagate = True
    logging.getLogger("gunicorn.access").handlers = []
    logging.getLogger("gunicorn.access").propagate = False

    _CONFIGURED = True


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields) -> None:
    """Log a record as ``event key=value ...`` with values quoted when needed."""
    parts = [event]
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, float):
            value = f"{value:.4f}"
        text = str(value)
        if " " in text or "=" in text:
            text = '"' + text.replace('"', "'") + '"'
        parts.append(f"{key}={text}")
    logger.log(level, " ".join(parts))
