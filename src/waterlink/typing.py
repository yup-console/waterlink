"""Common type aliases shared across the waterlink codebase.

Kept dependency-free so every other module can import from here without
risking circular imports.
"""

from __future__ import annotations

from typing import Any, TypeAlias

#: A single JSON object, i.e. a Lavalink REST/WS payload body.
JSONDict: TypeAlias = dict[str, Any]

#: Any value that can legally appear inside a JSON document.
JSONValue: TypeAlias = "str | int | float | bool | None | JSONDict | list[JSONValue]"

#: A full JSON payload, either an object or an array at the top level.
JSONPayload: TypeAlias = "JSONDict | list[JSONValue]"

__all__ = ["JSONDict", "JSONPayload", "JSONValue"]
