"""Node pool: manages multiple Lavalink nodes and picks the best one.

The pool is the main entry point applications interact with. It owns the
shared :class:`~waterlink.events.EventBus`, the aiohttp session, and every
registered :class:`~waterlink.node.Node`, and exposes selection strategies
for choosing which node a new player should use.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Iterable

import aiohttp

from .errors import ConfigurationError, NoAvailableNodeError
from .events import EventBus
from .node import Node

logger = logging.getLogger("waterlink.pool")

__all__ = ["NodePool", "RoutingStrategy"]


class RoutingStrategy(Enum):
    """How :meth:`NodePool.best_node` picks among healthy nodes."""

    LOWEST_LOAD = "lowest_load"
    """Pick the node with the lowest computed penalty score."""

    ROUND_ROBIN = "round_robin"
    """Cycle through ready nodes in registration order."""

    REGION = "region"
    """Prefer a node matching the requested region, falling back to load."""


class NodePool:
    """Owns and load-balances a collection of :class:`Node` instances."""

    def __init__(
        self,
        *,
        user_id: int,
        session: aiohttp.ClientSession | None = None,
        events: EventBus | None = None,
        default_strategy: RoutingStrategy = RoutingStrategy.LOWEST_LOAD,
    ) -> None:
        self.user_id = user_id
        self.events = events or EventBus()
        self._session = session
        self._owns_session = session is None
        self._nodes: dict[str, Node] = {}
        self._rr_cursor = 0
        self.default_strategy = default_strategy

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    @property
    def nodes(self) -> tuple[Node, ...]:
        return tuple(self._nodes.values())

    @property
    def ready_nodes(self) -> tuple[Node, ...]:
        return tuple(n for n in self._nodes.values() if n.is_ready)

    def get_node(self, name: str) -> Node | None:
        return self._nodes.get(name)

    async def add_node(
        self,
        *,
        name: str,
        host: str,
        port: int,
        password: str,
        secure: bool = False,
        region: str | None = None,
        resume_timeout_seconds: int = 60,
        connect: bool = True,
    ) -> Node:
        if name in self._nodes:
            raise ConfigurationError(f"A node named {name!r} is already registered")

        session = await self._ensure_session()
        node = Node(
            name=name,
            host=host,
            port=port,
            password=password,
            user_id=self.user_id,
            secure=secure,
            session=session,
            events=self.events,
            region=region,
            resume_timeout_seconds=resume_timeout_seconds,
        )
        self._nodes[name] = node
        if connect:
            await node.connect()
        return node

    async def remove_node(self, name: str) -> None:
        node = self._nodes.pop(name, None)
        if node is not None:
            await node.close()

    async def close(self) -> None:
        for node in self._nodes.values():
            await node.close()
        if self._owns_session and self._session is not None and not self._session.closed:
            await self._session.close()

    def best_node(
        self,
        *,
        strategy: RoutingStrategy | None = None,
        region: str | None = None,
        exclude: Iterable[Node] = (),
    ) -> Node:
        """Select the best available node under the given strategy.

        Raises :class:`NoAvailableNodeError` if no ready node qualifies.
        """

        strategy = strategy or self.default_strategy
        excluded_names = {n.name for n in exclude}
        candidates = [n for n in self.ready_nodes if n.name not in excluded_names]

        if not candidates:
            raise NoAvailableNodeError("No ready Lavalink node is available")

        if strategy is RoutingStrategy.ROUND_ROBIN:
            self._rr_cursor = (self._rr_cursor + 1) % len(candidates)
            return candidates[self._rr_cursor]

        if strategy is RoutingStrategy.REGION and region is not None:
            regional = [n for n in candidates if n.region == region]
            if regional:
                candidates = regional

        return min(candidates, key=lambda n: n.stats.penalty_score)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<NodePool nodes={len(self._nodes)} ready={len(self.ready_nodes)}>"
