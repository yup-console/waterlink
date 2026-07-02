"""Websocket connection lifecycle for a single Lavalink node.

This module owns the raw connect/read/reconnect loop and hands parsed
OP payloads to a callback. It has no knowledge of players or events; that
routing lives in :mod:`waterlink.node`, keeping this module small and
independently testable.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Awaitable, Callable

import aiohttp

from .backoff import ExponentialBackoff
from .errors import NodeConnectionError
from .typing import JSONDict

if TYPE_CHECKING:
    pass

logger = logging.getLogger("waterlink.websocket")

__all__ = ["NodeWebSocket"]

OpHandler = Callable[[JSONDict], Awaitable[None]]


class NodeWebSocket:
    """Manages the websocket connection to one Lavalink node.

    Reconnection is automatic with exponential backoff unless
    :meth:`close` is called explicitly. Each successful reconnect resets
    the backoff counter.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int,
        password: str,
        user_id: int,
        secure: bool = False,
        session: aiohttp.ClientSession,
        on_message: OpHandler,
        on_open: Callable[[], Awaitable[None]] | None = None,
        on_close: Callable[[int, str], Awaitable[None]] | None = None,
        on_reconnecting: Callable[[int, float], Awaitable[None]] | None = None,
        resume_session_id: str | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.secure = secure
        self._password = password
        self._user_id = user_id
        self._session = session
        self._on_message = on_message
        self._on_open = on_open
        self._on_close = on_close
        self._on_reconnecting = on_reconnecting
        self._resume_session_id = resume_session_id

        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._task: asyncio.Task[None] | None = None
        self._backoff = ExponentialBackoff()
        self._closing = False
        self._connected_event = asyncio.Event()

    @property
    def url(self) -> str:
        scheme = "wss" if self.secure else "ws"
        return f"{scheme}://{self.host}:{self.port}/v4/websocket"

    @property
    def is_connected(self) -> bool:
        return self._ws is not None and not self._ws.closed

    def set_resume_session_id(self, session_id: str | None) -> None:
        self._resume_session_id = session_id

    async def connect(self) -> None:
        """Start the connection loop as a background task, if not running."""

        self._closing = False
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name=f"waterlink-ws-{self.host}:{self.port}")
        await self._connected_event.wait()

    async def close(self) -> None:
        self._closing = True
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._task = None

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": self._password,
            "User-Id": str(self._user_id),
            "Client-Name": "waterlink",
        }
        if self._resume_session_id:
            headers["Session-Id"] = self._resume_session_id
        return headers

    async def _run(self) -> None:
        while not self._closing:
            try:
                await self._connect_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning("Node %s:%s websocket error: %s", self.host, self.port, exc)

            self._connected_event.clear()
            if self._closing:
                return

            delay = self._backoff.next_delay()
            attempt = self._backoff.attempt
            if self._on_reconnecting is not None:
                await self._on_reconnecting(attempt, delay)
            logger.info(
                "Reconnecting to node %s:%s in %.2fs (attempt %d)",
                self.host,
                self.port,
                delay,
                attempt,
            )
            await asyncio.sleep(delay)

    async def _connect_once(self) -> None:
        try:
            async with self._session.ws_connect(
                self.url, headers=self._headers(), heartbeat=30
            ) as ws:
                self._ws = ws
                self._backoff.reset()
                self._connected_event.set()
                if self._on_open is not None:
                    await self._on_open()

                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        await self._dispatch_raw(msg.data)
                    elif msg.type in (
                        aiohttp.WSMsgType.CLOSE,
                        aiohttp.WSMsgType.CLOSING,
                        aiohttp.WSMsgType.CLOSED,
                    ):
                        break
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        logger.warning("Node %s:%s websocket error frame", self.host, self.port)
                        break

                close_code = ws.close_code or 1000
                if self._on_close is not None:
                    await self._on_close(close_code, "connection closed")
        except aiohttp.ClientConnectionError as exc:
            raise NodeConnectionError(str(exc), node_name=f"{self.host}:{self.port}") from exc
        finally:
            self._ws = None

    async def _dispatch_raw(self, data: str) -> None:
        import json

        try:
            payload = json.loads(data)
        except ValueError:
            logger.warning("Received non-JSON payload from node %s:%s", self.host, self.port)
            return
        await self._on_message(payload)
