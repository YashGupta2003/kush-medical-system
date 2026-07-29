"""
Centralized logging system for Kush Medical System.
Provides structured logging across FastAPI API handlers, Celery background workers,
and core business services.
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional


def get_logger(name: str = "kush_medical") -> logging.Logger:
    """
    Returns a configured logger instance for the given module name.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Standard formatter
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] [%(filename)s:%(lineno)d]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # Rotating File Handler
    try:
        log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../logs"))
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "app.log")
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        logger.addHandler(file_handler)
    except Exception as e:
        console_handler.emit(
            logging.LogRecord(
                name=name,
                level=logging.WARNING,
                pathname=__file__,
                lineno=45,
                msg=f"Could not initialize file log handler: {e}",
                args=(),
                exc_info=None,
            )
        )

    return logger


logger = get_logger()
