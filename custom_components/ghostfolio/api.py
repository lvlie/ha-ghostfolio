"""Lightweight async client for the Ghostfolio API."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = ClientTimeout(total=30)

# Ghostfolio answers with these when the access token is wrong or revoked.
_AUTH_STATUSES = (400, 401, 403)


class GhostfolioAuthError(Exception):
    """Raised when authentication with Ghostfolio fails."""


class GhostfolioApiError(Exception):
    """Raised when the Ghostfolio API returns an unexpected error."""


class _TokenExpiredError(Exception):
    """Internal signal that the cached JWT needs to be refreshed."""


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
        """Initialise the client for one Ghostfolio instance."""
        self._session = session
        self._base_url = url.rstrip("/")
        self._access_token = access_token
        self._verify_ssl = verify_ssl
        self._auth_token: str | None = None

    @property
    def base_url(self) -> str:
        """Return the base URL of the Ghostfolio instance."""
        return self._base_url

    async def _login(self) -> None:
        """Exchange the access token for a short-lived JWT."""
        url = f"{self._base_url}/api/v1/auth/anonymous"
        try:
            async with self._session.post(
                url,
                json={"accessToken": self._access_token},
                ssl=self._verify_ssl,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status in _AUTH_STATUSES:
                    raise GhostfolioAuthError(
                        f"Authentication rejected by Ghostfolio (HTTP {resp.status})"
                    )
                resp.raise_for_status()
                data = await resp.json()
        except TimeoutError as err:
            raise GhostfolioApiError("Timed out logging in to Ghostfolio") from err
        except ClientError as err:
            raise GhostfolioApiError(f"Login failed: {err}") from err

        token = data.get("authToken")
        if not token:
            raise GhostfolioAuthError("Ghostfolio did not return an auth token")
        self._auth_token = token

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET a JSON endpoint, logging in again once if the JWT expired."""
        if self._auth_token is None:
            await self._login()

        try:
            return await self._get_once(path, params)
        except _TokenExpiredError:
            self._auth_token = None
            await self._login()

        try:
            return await self._get_once(path, params)
        except _TokenExpiredError as err:
            raise GhostfolioAuthError(
                f"Ghostfolio rejected a freshly issued token for {path}"
            ) from err

    async def _get_once(self, path: str, params: dict[str, Any] | None) -> Any:
        """Perform a single authenticated GET request."""
        url = f"{self._base_url}{path}"
        headers = {"Authorization": f"Bearer {self._auth_token}"}
        try:
            async with self._session.get(
                url,
                headers=headers,
                params=params,
                ssl=self._verify_ssl,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise _TokenExpiredError
                if resp.status == 403:
                    raise GhostfolioAuthError(
                        f"Ghostfolio denied access to {path} (HTTP 403)"
                    )
                resp.raise_for_status()
                return await resp.json()
        except TimeoutError as err:
            raise GhostfolioApiError(f"Timed out requesting {path}") from err
        except ClientError as err:
            raise GhostfolioApiError(f"Request to {path} failed: {err}") from err

    async def async_validate(self) -> None:
        """Validate that the credentials work by performing a login."""
        await self._login()

    async def async_get_accounts(self) -> list[dict[str, Any]]:
        """Return the configured Ghostfolio accounts."""
        data = await self._get("/api/v1/account")
        if isinstance(data, dict):
            return data.get("accounts", [])
        return data or []

    async def async_get_user(self) -> dict[str, Any]:
        """Return the current user, including its settings."""
        return await self._get("/api/v1/user")

    async def async_get_details(self) -> dict[str, Any]:
        """Return the portfolio details (accounts, holdings and summary)."""
        return await self._get("/api/v1/portfolio/details")

    async def async_get_holdings(self, account_id: str | None = None) -> dict[str, Any]:
        """Return the holdings, optionally filtered to a single account."""
        params = {"accounts": account_id} if account_id else None
        return await self._get("/api/v1/portfolio/holdings", params=params)
