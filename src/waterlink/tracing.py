"""Structured, per-guild logging helpers.

Standard :mod:`logging` doesn't make it easy to consistently tag messages
with guild/node context. :class:`ContextLogger` wraps a logger and injects
that context as ``extra`` fields, and :func:`configure_logging` offers a
one-call way to set up sensible defaults for local development.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

__all__ = ["ContextLogger", "configure_logging", "get_logger"]


class ContextLogger(logging.LoggerAdapter):
    """A :class:`logging.LoggerAdapter` that merges bound context into
    every record's ``extra`` dict, e.g. ``guild_id`` and ``node``.
    """

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        extra = kwargs.setdefault("extra", {})
        extra.update(self.extra or {})
        return msg, kwargs

    def bind(self, **context: Any) -> "ContextLogger":
        merged = {**(self.extra or {}), **context}
        return ContextLogger(self.logger, merged)


def get_logger(name: str, **context: Any) -> ContextLogger:
    return ContextLogger(logging.getLogger(name), context)


_CONTEXT_FIELDS = ("guild_id", "node")


class _ContextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        parts = []
        for field in _CONTEXT_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                parts.append(f"{field}={value}")
        if parts:
            record.msg = f"[{' '.join(parts)}] {record.msg}"
        return super().format(record)


def configure_logging(level: int = logging.INFO, *, stream: Any = None) -> None:
    """Configure a reasonable default handler for the ``waterlink`` logger
    tree. Safe to call multiple times; only installs a handler once.
    """

    root = logging.getLogger("waterlink")
    root.setLevel(level)
    if any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        return

    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(
        _ContextFormatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    )
    root.addHandler(handler)
    root.propagate = False
