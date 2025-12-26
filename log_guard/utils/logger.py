"""
Centralized logging utility for LogGuard.

Provides consistent logging across all components with file and console handlers.
"""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str,
    log_level: str = 'INFO',
    log_file: Optional[str] = None,
    log_format: Optional[str] = None
) -> logging.Logger:
    """
    Set up a logger with console and optional file handlers.

    param name: Logger name (typically __name__ of the module).
    param log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    param log_file: Optional file path to write logs to.
    param log_format: Optional custom log format string.
    """
    logger = logging.getLogger(name)

    # Avoid adding handlers multiple times if logger already exists.
    if logger.hasHandlers():
        return logger

    logger.setLevel(getattr(logging, log_level.upper()))

    # Default format.
    if log_format is None:
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    formatter = logging.Formatter(log_format, datefmt='%Y-%m-%d %H:%M:%S')

    # Console handler (stdout).
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if specified).
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get an existing logger by name.

    param name: Logger name.
    """
    return logging.getLogger(name)