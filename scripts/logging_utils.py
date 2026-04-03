#!/usr/bin/env python3
"""Shared logging utilities for IntelliFL scripts.

Provides consistent logging across all scripts with file and console output.
"""

import logging
import sys
from pathlib import Path


def setup_logger(name: str, log_file: str | None = None) -> logging.Logger:
    """Set up a logger with both console and file handlers.

    Args:
        name: Logger name (typically __name__).
        log_file: Optional log file name (without path). If provided,
            logs will be written to logs/{log_file}.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Console handler (INFO level)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler (DEBUG level) if log file specified
    if log_file:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        log_path = log_dir / log_file

        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        logger.debug(f"Logging to {log_path}")

    return logger
