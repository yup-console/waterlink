"""Discord library detection and a unified voice-client adapter.

waterlink doesn't hard-depend on any single Discord library. Instead it
auto-detects whichever one is installed (discord.py, py-cord, nextcord, or
disnake all expose a compatible ``Client``/gateway shape) and adapts to it
through a small shim so the rest of the codebase never has to branch on
which library the host application chose.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from typing import Any, Protocol

from .errors import LibraryNotSupportedError

logger = logging.getLogger("waterlink.compat")

__all__ = ["DetectedLibrary", "detect_library", "VoiceClientBase"]

_CANDIDATES = ("discord", "nextcord", "disnake")
# py-cord also imports as `discord`, so it's disambiguated by module attrs.


@dataclass(slots=True, frozen=True)
class DetectedLibrary:
    name: str
    module: Any
    is_pycord: bool = False


def detect_library() -> DetectedLibrary:
    """Locate whichever supported Discord library is installed.

    Preference order is stable but not meaningful beyond "first match" —
    only one such library should realistically be installed at a time.
    """

    for module_name in _CANDIDATES:
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue

        if module_name == "discord":
            is_pycord = hasattr(module, "SinkFilters") or "pycord" in getattr(
                module, "__title__", ""
            ).lower()
            label = "py-cord" if is_pycord else "discord.py"
            return DetectedLibrary(name=label, module=module, is_pycord=is_pycord)

        return DetectedLibrary(name=module_name, module=module)

    raise LibraryNotSupportedError(
        "No supported Discord library found. Install one of: "
        "discord.py, py-cord, nextcord, disnake."
    )


class VoiceClientBase(Protocol):
    """The subset of a library's ``VoiceProtocol``/``VoiceClient`` interface
    that waterlink's voice adapter relies on. Real voice clients created by
    :mod:`waterlink.voice` satisfy this structurally.
    """

    guild: Any
    channel: Any

    async def on_voice_state_update(self, data: dict[str, Any]) -> None: ...
    async def on_voice_server_update(self, data: dict[str, Any]) -> None: ...
