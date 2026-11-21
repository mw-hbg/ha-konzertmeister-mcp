"""Client for the official Konzertmeister API (machine-to-machine, "m2m").

Documentation: https://konzertmeister.app/en/help/konzertmeister-api
OpenAPI:       https://rest.konzertmeister.app/v3/api-docs/m2m

Every request carries the association's API key in the header
X-KM-ORG-API-KEY. The key is never logged and never part of an error text.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

BASE_URL = os.environ.get("KM_API_BASE", "https://rest.konzertmeister.app")
KEY_HEADER = "X-KM-ORG-API-KEY"
TIMEOUT = httpx.Timeout(25.0, connect=10.0)
USER_AGENT = (
    f"KonzertmeisterMCP/{os.environ.get('APP_VERSION', 'dev')} "
    "(+https://github.com/mw-hbg/ha-konzertmeister-mcp)"
)

PATH_APPOINTMENTS = "/api/v4/org/m2m/appointments"
PATH_MEMBERS = "/api/v4/org/m2m/members"
PATH_REPLIES = "/api/v4/att/m2m/{app_id}"
PATH_ATTENDANCE = "/api/v2/attreal/m2m/{app_id}"
PATH_CREATE = "/api/v4/app/m2m/create"
PATH_ADD_MEMBER = "/api/v4/org/m2m/addmember"
PATH_UPDATE_MEMBER = "/api/v4/org/m2m/updatemember"


class ApiError(Exception):
    """kind: 'auth' (key wrong or revoked), 'forbidden', 'not_found',
    'rate_limit', 'bad_request', 'server', 'network'."""

    def __init__(self, kind: str, status: int = 0, detail: str = "") -> None:
        super().__init__(f"{kind} {status} {detail}".strip())
        self.kind = kind
        self.status = status
        self.detail = detail


def _kind(status: int) -> str:
    if status == 401:
        return "auth"
    if status == 403:
        return "forbidden"
    if status == 404:
        return "not_found"
    if status == 429:
        return "rate_limit"
    if 400 <= status < 500:
        return "bad_request"
    return "server"


def _detail(response: httpx.Response) -> str:
    """A short, key-free hint from an error answer."""
    try:
        data = response.json()
    except ValueError:
        return ""
    if isinstance(data, dict):
        for key in ("message", "error", "detail", "title"):
            if isinstance(data.get(key), str):
                return data[key][:200]
    return ""


class Konzertmeister:
    def __init__(self, api_key: str, base_url: str = BASE_URL, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={KEY_HEADER: api_key, "User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=TIMEOUT,
            transport=transport,
            follow_redirects=False,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _call(self, method: str, path: str, body: Any = None) -> Any:
        try:
            response = await self._client.request(method, path, json=body)
        except httpx.HTTPError as exc:
            raise ApiError("network", 0, type(exc).__name__) from None
        if response.status_code >= 300:
            raise ApiError(_kind(response.status_code), response.status_code, _detail(response))
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return None

    # reading -----------------------------------------------------------------
    async def appointments(self, filters: dict) -> list[dict]:
        data = await self._call("POST", PATH_APPOINTMENTS, filters)
        return [a for a in data or [] if isinstance(a, dict)]

    async def members(self) -> list[dict]:
        data = await self._call("GET", PATH_MEMBERS)
        return [m for m in data or [] if isinstance(m, dict)]

    async def replies(self, app_id: int) -> list[dict]:
        data = await self._call("GET", PATH_REPLIES.format(app_id=int(app_id)))
        return [r for r in data or [] if isinstance(r, dict)]

    async def attendance(self, app_id: int) -> list[dict]:
        data = await self._call("GET", PATH_ATTENDANCE.format(app_id=int(app_id)))
        return [r for r in data or [] if isinstance(r, dict)]

    # writing -----------------------------------------------------------------
    async def create_appointment(self, body: dict) -> dict:
        data = await self._call("POST", PATH_CREATE, body)
        return data if isinstance(data, dict) else {}

    async def add_member(self, body: dict) -> None:
        await self._call("POST", PATH_ADD_MEMBER, body)

    async def update_member(self, body: dict) -> None:
        await self._call("POST", PATH_UPDATE_MEMBER, body)
