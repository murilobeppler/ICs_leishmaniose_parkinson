"""Logging estruturado e sanitizado para os pacotes científicos."""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

from ic_core.config import CoreSettings

_SENSITIVE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"), "[REDACTED_ID]"),
    (
        re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*([^\s,;]+)"),
        r"\1=[REDACTED]",
    ),
)


def sanitize_log_text(text: str) -> str:
    """Remove padrões sensíveis (tokens, CPFs/identificadores brutos) de mensagens de log."""
    cleaned = text
    for pattern, replacement in _SENSITIVE_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned


class StructuredFormatter(logging.Formatter):
    """Formatter que suporta saída JSON estruturada ou console legível."""

    def __init__(self, fmt_mode: str = "console") -> None:
        super().__init__()
        self.fmt_mode = fmt_mode

    def format(self, record: logging.LogRecord) -> str:
        message = sanitize_log_text(record.getMessage())
        timestamp = datetime.fromtimestamp(record.created, tz=UTC).isoformat()

        if self.fmt_mode == "json":
            payload: dict[str, Any] = {
                "timestamp": timestamp,
                "level": record.levelname,
                "logger": record.name,
                "message": message,
            }
            context = getattr(record, "context", None)
            if isinstance(context, dict):
                payload["context"] = {str(k): sanitize_log_text(str(v)) for k, v in context.items()}
            if record.exc_info:
                payload["exception"] = self.formatException(record.exc_info)
            return json.dumps(payload, ensure_ascii=False)

        context_str = ""
        context = getattr(record, "context", None)
        if isinstance(context, dict) and context:
            pairs = " ".join(f"{k}={sanitize_log_text(str(v))}" for k, v in sorted(context.items()))
            context_str = f" [{pairs}]"
        return f"{timestamp} | {record.levelname:<7} | {record.name} | {message}{context_str}"


def get_logger(name: str, settings: CoreSettings | None = None) -> logging.Logger:
    """Retorna um logger configurado conforme `CoreSettings`."""
    cfg = settings or CoreSettings()
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, cfg.ic_log_level))
    logger.propagate = False

    if not logger.handlers:
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(StructuredFormatter(fmt_mode=cfg.ic_log_format))
        logger.addHandler(stream_handler)
    else:
        for existing_handler in logger.handlers:
            existing_handler.setFormatter(StructuredFormatter(fmt_mode=cfg.ic_log_format))

    return logger
