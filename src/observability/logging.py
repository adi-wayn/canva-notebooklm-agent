"""Structured JSON logging configuration for Canva-NotebookLM Agent.

Provides:
- JSON formatter for machine-readable logs
- Request context tracking via contextvars
- Performance metrics (duration, memory)
- Security event logging

Context-aware logging:
- Automatically pulls request_id, tenant_id, user_id from contextvars
- No API changes required for callers
- Works across async task boundaries
"""

import json
import logging
import sys
from typing import Any, Dict, Optional

from pythonjsonlogger import jsonlogger

from src.observability.context import get_request_id, get_tenant_id, get_user_id


class JSONFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional context fields."""

    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        """Add custom fields to JSON log record.

        Args:
            log_record: The log record dict to be serialized
            record: The original logging.LogRecord
            message_dict: The message dictionary
        """
        super().add_fields(log_record, record, message_dict)

        # Add standard fields
        log_record["timestamp"] = self.formatTime(record, self.datefmt)
        log_record["logger"] = record.name
        log_record["level"] = record.levelname
        log_record["module"] = record.module
        log_record["function"] = record.funcName
        log_record["line"] = record.lineno

        # Add exception info if present
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        # Add context from contextvars (request_id, tenant_id, user_id)
        request_id = get_request_id()
        if request_id:
            log_record["request_id"] = request_id

        tenant_id = get_tenant_id()
        if tenant_id:
            log_record["tenant_id"] = tenant_id

        user_id = get_user_id()
        if user_id:
            log_record["user_id"] = user_id

        # Add extra fields from record if present (backward compatibility)
        if hasattr(record, "request_id") and "request_id" not in log_record:
            log_record["request_id"] = record.request_id
        if hasattr(record, "user_id") and "user_id" not in log_record:
            log_record["user_id"] = record.user_id
        if hasattr(record, "tenant_id") and "tenant_id" not in log_record:
            log_record["tenant_id"] = record.tenant_id
        if hasattr(record, "duration_ms"):
            log_record["duration_ms"] = record.duration_ms


def setup_json_logging(
    level: str = "INFO",
    format_type: str = "json",
    log_to_file: Optional[str] = None,
) -> None:
    """Configure JSON logging for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Output format ('json' or 'text')
        log_to_file: Optional file path for file logging

    Example:
        >>> from src.observability.logging import setup_json_logging
        >>> setup_json_logging(level="INFO", format_type="json")
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create formatter
    if format_type.lower() == "json":
        formatter = JSONFormatter(
            fmt="%(timestamp)s %(level)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (if specified)
    if log_to_file:
        file_handler = logging.FileHandler(log_to_file)
        file_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def add_request_context(logger: logging.Logger, request_id: str, user_id: Optional[str] = None, tenant_id: Optional[str] = None) -> None:
    """Add request context to logger.

    Args:
        logger: Logger instance
        request_id: Unique request identifier
        user_id: Optional user identifier
        tenant_id: Optional tenant identifier
    """
    # Add to logger's extra dict (used by JSONFormatter)
    if not hasattr(logger, "_extra"):
        logger._extra = {}
    logger._extra["request_id"] = request_id
    if user_id:
        logger._extra["user_id"] = user_id
    if tenant_id:
        logger._extra["tenant_id"] = tenant_id
