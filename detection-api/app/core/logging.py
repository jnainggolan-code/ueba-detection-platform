"""Structured logging configuration for the detection API."""

import logging
import sys

from app.core.config import settings


def setup_logging() -> None:
    """Configure structured logging for the application."""
    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    date_format = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format=log_format,
        datefmt=date_format,
        stream=sys.stdout,
    )

    # Quiet noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
