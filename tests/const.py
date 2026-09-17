"""Shared fixtures data for the Ghostfolio tests."""

from __future__ import annotations

from typing import Any

MOCK_URL = "http://ghostfolio.local:3333"
MOCK_TOKEN = "0123456789abcdef"

MOCK_USER: dict[str, Any] = {"settings": {"baseCurrency": "EUR"}}

MOCK_DETAILS: dict[str, Any] = {
    "summary": {"baseCurrency": "EUR", "currentValueInBaseCurrency": 1500.0},
    "accounts": {
        "acc-1": {
            "name": "Brokerage",
            "currency": "EUR",
            "valueInBaseCurrency": 1000,
        },
        "acc-2": {"name": "Crypto", "currency": "EUR", "valueInBaseCurrency": 500},
    },
    "holdings": {
        "AAPL": {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "quantity": 5,
            "marketPrice": 200,
            "currency": "EUR",
            "dataSource": "YAHOO",
            "assetClass": "EQUITY",
            "accounts": [
                {
                    "id": "acc-1",
                    "name": "Brokerage",
                    "valueInBaseCurrency": 1000,
                    "quantity": 5,
                }
            ],
        },
        "BTC": {
            "symbol": "BTC",
            "name": "Bitcoin",
            "quantity": 0.01,
            "marketPrice": 50000,
            "currency": "EUR",
            "dataSource": "COINGECKO",
            "assetClass": "CRYPTO",
            "accounts": [
                {
                    "id": "acc-2",
                    "name": "Crypto",
                    "valueInBaseCurrency": 500,
                    "quantity": 0.01,
                }
            ],
        },
        "SOLD": {
            "symbol": "SOLD",
            "name": "Sold out position",
            "quantity": 0,
            "marketPrice": 10,
            "currency": "EUR",
            "accounts": [
                {"id": "acc-1", "name": "Brokerage", "valueInBaseCurrency": 0}
            ],
        },
    },
}
