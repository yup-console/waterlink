"""Async REST client for a single Lavalink node (v4 HTTP API)."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .errors import RESTRequestError, RESTResponseError
from .typing import JSONDict

logger = logging.getLogger("waterlink.rest")

__all__ = ["RESTClient"]


class RESTClient:
    """Thin wrapper around a node's HTTP API.

    All methods return parsed JSON (as :data:`JSONDict` / lists) and raise
    :class:`~waterlink.errors.RESTResponseError` on non-2xx responses, or
    :class:`~waterlink.errors.RESTRequestError` if the request could not be
    made at all (connection refused, timeout, ...).
    """

    def __init__(
        self,
        *,
        host: str,
        port: int,
        password: str,
        secure: bool = False,
        session: aiohttp.ClientSession,
    ) -> None:
        self.host = host
        self.port = port
        self.secure = secure
        self._password = password
        self._session = session

    @property
    def base_url(self) -> str:
        scheme = "https" if self.secure else "http"
        return f"{scheme}://{self.host}:{self.port}"

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": self._password}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: JSONDict | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        # Always ask Lavalink for the full error trace. It's a no-op on
        # success and costs nothing, but turns an opaque generic
        # {"message": "Bad Request"} into an actual diagnosable stack
        # trace when something does go wrong.
        merged_params: dict[str, Any] = {"trace": "true"}
        if params:
            merged_params.update(params)
        try:
            async with self._session.request(
                method, url, json=json, params=merged_params, headers=self._headers
            ) as resp:
                if resp.status == 204:
                    return None
                if resp.status >= 400:
                    body = await _safe_body(resp)
                    raise RESTResponseError(
                        f"{method} {path} failed", status=resp.status, body=body
                    )
                if resp.content_type == "application/json":
                    return await resp.json()
                return await resp.text()
        except aiohttp.ClientError as exc:
            raise RESTRequestError(f"{method} {path} could not be completed: {exc}") from exc

    # -- track loading ----------------------------------------------------- #

    async def load_tracks(self, identifier: str) -> JSONDict:
        return await self._request("GET", "/v4/loadtracks", params={"identifier": identifier})

    async def decode_track(self, encoded: str) -> JSONDict:
        return await self._request("GET", "/v4/decodetrack", params={"encodedTrack": encoded})

    async def decode_tracks(self, encoded: list[str]) -> list[JSONDict]:
        return await self._request("POST", "/v4/decodetracks", json=encoded)

    # -- players ------------------------------------------------------------ #

    async def get_players(self, session_id: str) -> list[JSONDict]:
        return await self._request("GET", f"/v4/sessions/{session_id}/players")

    async def get_player(self, session_id: str, guild_id: int) -> JSONDict:
        return await self._request("GET", f"/v4/sessions/{session_id}/players/{guild_id}")

    async def update_player(
        self,
        session_id: str,
        guild_id: int,
        *,
        payload: JSONDict,
        no_replace: bool = False,
    ) -> JSONDict:
        return await self._request(
            "PATCH",
            f"/v4/sessions/{session_id}/players/{guild_id}",
            json=payload,
            params={"noReplace": str(no_replace).lower()},
        )

    async def destroy_player(self, session_id: str, guild_id: int) -> None:
        await self._request("DELETE", f"/v4/sessions/{session_id}/players/{guild_id}")

    async def update_session(self, session_id: str, *, payload: JSONDict) -> JSONDict:
        return await self._request("PATCH", f"/v4/sessions/{session_id}", json=payload)

    # -- info / diagnostics -------------------------------------------------- #

    async def get_info(self) -> JSONDict:
        return await self._request("GET", "/v4/info")

    async def get_stats(self) -> JSONDict:
        return await self._request("GET", "/v4/stats")

    async def get_version(self) -> str:
        return await self._request("GET", "/version")

    async def get_route_planner_status(self) -> JSONDict:
        return await self._request("GET", "/v4/routeplanner/status")

    async def free_route_planner_address(self, address: str) -> None:
        await self._request(
            "POST", "/v4/routeplanner/free/address", json={"address": address}
        )

    async def free_all_route_planner_addresses(self) -> None:
        await self._request("POST", "/v4/routeplanner/free/all")


async def _safe_body(resp: aiohttp.ClientResponse) -> Any:
    try:
        if resp.content_type == "application/json":
            return await resp.json()
        return await resp.text()
    except Exception:  # noqa: BLE001
        return None
