"""Structured logging configuration for Eko AI."""

import logging
import sys
from typing import Any, Dict


class StructuredFormatter(logging.Formatter):
    """JSON-like formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields if present
        if hasattr(record, "lead_id"):
            log_data["lead_id"] = record.lead_id
        if hasattr(record, "agent"):
            log_data["agent"] = record.agent
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return f"[{log_data['timestamp']}] {log_data['level']} | {log_data['logger']} | {log_data['message']}"


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure application-wide logging."""
    logger = logging.getLogger("eko_ai")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())
        logger.addHandler(handler)
    
    return logger
