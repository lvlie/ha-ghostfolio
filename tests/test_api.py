"""Tests for the Ghostfolio REST client."""

from __future__ import annotations

from http import HTTPStatus

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ghostfolio.api import (
    GhostfolioApiError,
    GhostfolioAuthError,
    GhostfolioClient,
)

from .const import MOCK_TOKEN, MOCK_URL

LOGIN_URL = f"{MOCK_URL}/api/v1/auth/anonymous"
USER_URL = f"{MOCK_URL}/api/v1/user"


def _client(hass: HomeAssistant) -> GhostfolioClient:
    return GhostfolioClient(
        session=async_get_clientsession(hass),
        url=f"{MOCK_URL}/",
        access_token=MOCK_TOKEN,
    )


async def test_base_url_strips_trailing_slash(hass: HomeAssistant) -> None:
    """The configured URL is normalised once, at construction time."""
    assert _client(hass).base_url == MOCK_URL


async def test_login_and_get(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A successful login is reused for subsequent requests."""
    aioclient_mock.post(LOGIN_URL, json={"authToken": "jwt-1"})
    aioclient_mock.get(USER_URL, json={"settings": {"baseCurrency": "EUR"}})

    client = _client(hass)
    assert await client.async_get_user() == {"settings": {"baseCurrency": "EUR"}}
    assert await client.async_get_user() == {"settings": {"baseCurrency": "EUR"}}

    # Only one login for two calls.
    assert len([call for call in aioclient_mock.mock_calls if call[0] == "POST"]) == 1
    assert aioclient_mock.mock_calls[-1][3]["Authorization"] == "Bearer jwt-1"


@pytest.mark.parametrize(
    "status",
    [HTTPStatus.BAD_REQUEST, HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN],
)
async def test_login_rejected(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, status: HTTPStatus
) -> None:
    """A rejected access token raises an auth error, not a generic one."""
    aioclient_mock.post(LOGIN_URL, status=status)

    with pytest.raises(GhostfolioAuthError):
        await _client(hass).async_validate()


async def test_login_without_token_in_response(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A 200 response without a token is still an auth failure."""
    aioclient_mock.post(LOGIN_URL, json={})

    with pytest.raises(GhostfolioAuthError):
        await _client(hass).async_validate()


async def test_server_error_raises_api_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Server-side failures surface as API errors so HA retries."""
    aioclient_mock.post(LOGIN_URL, json={"authToken": "jwt-1"})
    aioclient_mock.get(USER_URL, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    with pytest.raises(GhostfolioApiError):
        await _client(hass).async_get_user()


async def test_expired_token_is_refreshed_once(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A 401 on a data call triggers a single re-login and a retry."""
    aioclient_mock.post(LOGIN_URL, json={"authToken": "jwt-1"})
    aioclient_mock.get(USER_URL, status=HTTPStatus.UNAUTHORIZED)

    client = _client(hass)
    # Prime the client with a token, then make the endpoint start returning 401.
    with pytest.raises(GhostfolioAuthError):
        await client.async_get_user()

    logins = [call for call in aioclient_mock.mock_calls if call[0] == "POST"]
    assert len(logins) == 2


async def test_forbidden_on_data_call_is_auth_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A 403 means the token is not allowed to read the endpoint."""
    aioclient_mock.post(LOGIN_URL, json={"authToken": "jwt-1"})
    aioclient_mock.get(USER_URL, status=HTTPStatus.FORBIDDEN)

    with pytest.raises(GhostfolioAuthError):
        await _client(hass).async_get_user()
