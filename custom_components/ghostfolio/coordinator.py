"""DataUpdateCoordinator for Ghostfolio."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GhostfolioApiError, GhostfolioAuthError, GhostfolioClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class GhostfolioCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches portfolio data from Ghostfolio on a schedule."""

    def __init__(self, hass: HomeAssistant, client: GhostfolioClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            details = await self.client.async_get_details()
        except GhostfolioAuthError as err:
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except GhostfolioApiError as err:
            raise UpdateFailed(f"API error: {err}") from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Unexpected error fetching portfolio: {err}") from err

        return _normalise(details)


def _normalise(details: dict[str, Any]) -> dict[str, Any]:
    """Reshape the raw /portfolio/details response into a stable structure.

    Output:
        {
            "currency": "USD",
            "total_value": 12345.67,
            "accounts": {account_id: {"name": ..., "currency": ..., "value": ...}},
            "positions": [
                {
                    "account_id": ..., "account_name": ...,
                    "symbol": ..., "name": ...,
                    "quantity": ..., "market_price": ...,
                    "value": ..., "currency": ...,
                    "data_source": ..., "asset_class": ...,
                },
                ...
            ],
        }
    """
    accounts_raw = details.get("accounts") or {}
    holdings_raw = details.get("holdings") or {}
    summary = details.get("summary") or {}

    if isinstance(accounts_raw, list):
        accounts_iter = ((a.get("id"), a) for a in accounts_raw)
    else:
        accounts_iter = accounts_raw.items()

    accounts: dict[str, dict[str, Any]] = {}
    for acc_id, acc in accounts_iter:
        if not acc_id:
            continue
        accounts[acc_id] = {
            "name": acc.get("name") or acc_id,
            "currency": acc.get("currency"),
            "value": acc.get("valueInBaseCurrency", acc.get("value")),
            "balance": acc.get("balanceInBaseCurrency", acc.get("balance")),
        }

    if isinstance(holdings_raw, list):
        holdings_iter = holdings_raw
    else:
        holdings_iter = list(holdings_raw.values())

    base_currency = summary.get("baseCurrency") or summary.get("currency") or "USD"
    total_value = summary.get("currentValueInBaseCurrency")
    if total_value is None:
        total_value = summary.get("currentValue")
    if total_value is None:
        total_value = sum(
            (acc.get("value") or 0) for acc in accounts.values() if acc.get("value")
        )

    positions: list[dict[str, Any]] = []
    for holding in holdings_iter:
        if not isinstance(holding, dict):
            continue
        symbol = holding.get("symbol") or holding.get("name")
        if not symbol:
            continue
        quantity = holding.get("quantity") or 0
        market_price = holding.get("marketPrice") or holding.get("netPerformance")
        currency = holding.get("currency") or base_currency
        data_source = holding.get("dataSource")
        asset_class = holding.get("assetClass") or holding.get("assetSubClass")

        holding_accounts = holding.get("accounts") or []
        if not holding_accounts:
            value = (
                holding.get("valueInBaseCurrency")
                or holding.get("value")
                or (quantity * market_price if quantity and market_price else 0)
            )
            positions.append(
                {
                    "account_id": None,
                    "account_name": "Portfolio",
                    "symbol": symbol,
                    "name": holding.get("name") or symbol,
                    "quantity": quantity,
                    "market_price": market_price,
                    "value": value,
                    "currency": currency,
                    "data_source": data_source,
                    "asset_class": asset_class,
                }
            )
            continue

        for acc_ref in holding_accounts:
            if not isinstance(acc_ref, dict):
                continue
            acc_id = acc_ref.get("id")
            acc_name = acc_ref.get("name") or (
                accounts.get(acc_id, {}).get("name") if acc_id else None
            ) or "Portfolio"
            acc_value = (
                acc_ref.get("valueInBaseCurrency")
                or acc_ref.get("value")
                or 0
            )
            acc_quantity = acc_ref.get("quantity")
            if acc_quantity is None:
                acc_quantity = quantity
            positions.append(
                {
                    "account_id": acc_id,
                    "account_name": acc_name,
                    "symbol": symbol,
                    "name": holding.get("name") or symbol,
                    "quantity": acc_quantity,
                    "market_price": market_price,
                    "value": acc_value,
                    "currency": currency,
                    "data_source": data_source,
                    "asset_class": asset_class,
                }
            )

    return {
        "currency": base_currency,
        "total_value": total_value or 0,
        "accounts": accounts,
        "positions": positions,
    }
