from __future__ import annotations

import pytest

from waterlink.errors import ConfigurationError, NoAvailableNodeError
from waterlink.node import NodeStats
from waterlink.pool import NodePool, RoutingStrategy


class _FakeNode:
    def __init__(self, name: str, ready: bool, penalty: float, region: str | None = None) -> None:
        self.name = name
        self._ready = ready
        self.region = region
        self.stats = NodeStats()
        self.stats.playing_players = 0
        self._penalty = penalty

    @property
    def is_ready(self) -> bool:
        return self._ready

    class _Stats:
        pass


def test_best_node_raises_when_none_ready():
    pool = NodePool(user_id=1)
    with pytest.raises(NoAvailableNodeError):
        pool.best_node()


def test_add_node_duplicate_name_raises():
    import asyncio

    async def run():
        pool = NodePool(user_id=1)
        pool._nodes["main"] = object()  # type: ignore[assignment]
        with pytest.raises(ConfigurationError):
            await pool.add_node(name="main", host="localhost", port=2333, password="x", connect=False)

    asyncio.run(run())


def test_best_node_picks_lowest_penalty():
    pool = NodePool(user_id=1)

    class Node:
        def __init__(self, name, penalty):
            self.name = name
            self.region = None
            self.is_ready = True
            self.stats = type("S", (), {"penalty_score": penalty})()

    low = Node("low", 1.0)
    high = Node("high", 5.0)
    pool._nodes = {"low": low, "high": high}  # type: ignore[assignment]

    chosen = pool.best_node(strategy=RoutingStrategy.LOWEST_LOAD)
    assert chosen.name == "low"


def test_best_node_round_robin_cycles():
    pool = NodePool(user_id=1)

    class Node:
        def __init__(self, name):
            self.name = name
            self.region = None
            self.is_ready = True
            self.stats = type("S", (), {"penalty_score": 0.0})()

    a, b = Node("a"), Node("b")
    pool._nodes = {"a": a, "b": b}  # type: ignore[assignment]

    picks = [pool.best_node(strategy=RoutingStrategy.ROUND_ROBIN).name for _ in range(4)]
    # Should alternate between the two candidates.
    assert len(set(picks)) == 2
