"""Lightweight async client for the Ghostfolio API."""
from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientResponseError, ClientSession, ClientTimeout

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = ClientTimeout(total=30)


class GhostfolioAuthError(Exception):
    """Raised when authentication with Ghostfolio fails."""


class GhostfolioApiError(Exception):
    """Raised when the Ghostfolio API returns an unexpected error."""


class GhostfolioClient:
    """Minimal Ghostfolio REST client.

    Authenticates with a security/access token (the same one shown when an
    anonymous user signs up) and exchanges it for a short-lived JWT.
    """

    def __init__(
        self,
        session: ClientSession,
        url: str,
        access_token: str,
        verify_ssl: bool = True,
    ) -> None:
        self._session = session
        self._base_url = url.rstrip("/")
        self._access_token = access_token
        self._verify_ssl = verify_ssl
        self._auth_token: str | None = None

    @property
    def base_url(self) -> str:
        return self._base_url

    async def _login(self) -> None:
        url = f"{self._base_url}/api/v1/auth/anonymous"
        try:
            async with self._session.post(
                url,
                json={"accessToken": self._access_token},
                ssl=self._verify_ssl,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status in (400, 401, 403):
                    raise GhostfolioAuthError(
                        f"Authentication rejected by Ghostfolio (HTTP {resp.status})"
                    )
                resp.raise_for_status()
                data = await resp.json()
        except ClientResponseError as err:
            raise GhostfolioApiError(f"Login failed: {err}") from err

        token = data.get("authToken")
        if not token:
            raise GhostfolioAuthError("Ghostfolio did not return an auth token")
        self._auth_token = token

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if self._auth_token is None:
            await self._login()

        url = f"{self._base_url}{path}"
        headers = {"Authorization": f"Bearer {self._auth_token}"}
        async with self._session.get(
            url,
            headers=headers,
            params=params,
            ssl=self._verify_ssl,
            timeout=_TIMEOUT,
        ) as resp:
            if resp.status == 401:
                # Token expired; re-login once and retry.
                self._auth_token = None
                await self._login()
                headers["Authorization"] = f"Bearer {self._auth_token}"
                async with self._session.get(
                    url,
                    headers=headers,
                    params=params,
                    ssl=self._verify_ssl,
                    timeout=_TIMEOUT,
                ) as retry:
                    retry.raise_for_status()
                    return await retry.json()
            resp.raise_for_status()
            return await resp.json()

    async def async_validate(self) -> None:
        """Validate that the credentials work by performing a login."""
        await self._login()

    async def async_get_accounts(self) -> list[dict[str, Any]]:
        data = await self._get("/api/v1/account")
        if isinstance(data, dict):
            return data.get("accounts", [])
        return data or []

    async def async_get_user(self) -> dict[str, Any]:
        return await self._get("/api/v1/user")

    async def async_get_details(self) -> dict[str, Any]:
        return await self._get("/api/v1/portfolio/details")

    async def async_get_holdings(
        self, account_id: str | None = None
    ) -> dict[str, Any]:
        params = {"accounts": account_id} if account_id else None
        return await self._get("/api/v1/portfolio/holdings", params=params)
