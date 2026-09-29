"""Configure concise application logging without document payloads."""

import logging

from app.core.config import get_settings


def configure_logging() -> None:
    """Set the process-wide log level and a consistent text format."""

    logging.basicConfig(
        level=get_settings().log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )