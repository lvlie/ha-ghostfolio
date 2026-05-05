"""Unit tests for the coordinator's response normalisation."""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _stub_aiohttp() -> None:
    if "aiohttp" in sys.modules:
        return
    aiohttp = types.ModuleType("aiohttp")

    class _ClientResponseError(Exception):
        pass

    class _ClientSession:
        pass

    class _ClientTimeout:
        def __init__(self, *args, **kwargs):
            pass

    aiohttp.ClientResponseError = _ClientResponseError
    aiohttp.ClientSession = _ClientSession
    aiohttp.ClientTimeout = _ClientTimeout
    sys.modules["aiohttp"] = aiohttp


def _stub_homeassistant() -> None:
    if "homeassistant" in sys.modules:
        return
    ha = types.ModuleType("homeassistant")
    helpers = types.ModuleType("homeassistant.helpers")
    update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")
    core = types.ModuleType("homeassistant.core")

    class _DataUpdateCoordinator:
        def __init__(self, *args, **kwargs):
            pass

        def __class_getitem__(cls, item):
            return cls

    class _UpdateFailed(Exception):
        pass

    update_coordinator.DataUpdateCoordinator = _DataUpdateCoordinator
    update_coordinator.UpdateFailed = _UpdateFailed
    core.HomeAssistant = object

    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.helpers"] = helpers
    sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator
    sys.modules["homeassistant.core"] = core


def _load_coordinator():
    _stub_aiohttp()
    _stub_homeassistant()
    # Load the file directly so we don't trigger custom_components/ghostfolio/__init__.py.
    spec = importlib.util.spec_from_file_location(
        "_gf_coordinator",
        REPO / "custom_components" / "ghostfolio" / "coordinator.py",
        submodule_search_locations=[],
    )
    module = importlib.util.module_from_spec(spec)
    # The coordinator imports `.api` and `.const` relatively; satisfy those by
    # loading them as a stand-alone package first.
    pkg = types.ModuleType("_gf_pkg")
    pkg.__path__ = [str(REPO / "custom_components" / "ghostfolio")]
    sys.modules["_gf_pkg"] = pkg

    for sub in ("const", "api"):
        sub_spec = importlib.util.spec_from_file_location(
            f"_gf_pkg.{sub}",
            REPO / "custom_components" / "ghostfolio" / f"{sub}.py",
        )
        sub_mod = importlib.util.module_from_spec(sub_spec)
        sys.modules[f"_gf_pkg.{sub}"] = sub_mod
        sub_spec.loader.exec_module(sub_mod)

    # Rewrite the relative imports by loading coordinator.py source and
    # exec'ing it inside the fake package.
    coord_spec = importlib.util.spec_from_file_location(
        "_gf_pkg.coordinator",
        REPO / "custom_components" / "ghostfolio" / "coordinator.py",
    )
    coord_mod = importlib.util.module_from_spec(coord_spec)
    sys.modules["_gf_pkg.coordinator"] = coord_mod
    coord_spec.loader.exec_module(coord_mod)
    return coord_mod


_normalise = _load_coordinator()._normalise


def test_normalise_with_per_account_holdings():
    raw = {
        "summary": {"baseCurrency": "USD", "currentValueInBaseCurrency": 1500.0},
        "accounts": {
            "acc-1": {"name": "Brokerage", "currency": "USD", "valueInBaseCurrency": 1000},
            "acc-2": {"name": "Crypto", "currency": "USD", "valueInBaseCurrency": 500},
        },
        "holdings": {
            "AAPL": {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "quantity": 5,
                "marketPrice": 200,
                "currency": "USD",
                "dataSource": "YAHOO",
                "assetClass": "EQUITY",
                "accounts": [
                    {"id": "acc-1", "name": "Brokerage", "valueInBaseCurrency": 1000, "quantity": 5},
                ],
            },
            "BTC": {
                "symbol": "BTC",
                "name": "Bitcoin",
                "quantity": 0.01,
                "marketPrice": 50000,
                "currency": "USD",
                "dataSource": "COINGECKO",
                "assetClass": "CRYPTO",
                "accounts": [
                    {"id": "acc-2", "name": "Crypto", "valueInBaseCurrency": 500, "quantity": 0.01},
                ],
            },
        },
    }

    result = _normalise(raw)

    assert result["currency"] == "USD"
    assert result["total_value"] == 1500.0
    assert set(result["accounts"]) == {"acc-1", "acc-2"}
    assert len(result["positions"]) == 2

    aapl = next(p for p in result["positions"] if p["symbol"] == "AAPL")
    assert aapl["account_id"] == "acc-1"
    assert aapl["account_name"] == "Brokerage"
    assert aapl["value"] == 1000


def test_normalise_falls_back_to_quantity_times_price():
    raw = {
        "summary": {},
        "accounts": {},
        "holdings": [
            {
                "symbol": "VOO",
                "name": "Vanguard S&P 500",
                "quantity": 2,
                "marketPrice": 400,
                "currency": "USD",
            }
        ],
    }
    result = _normalise(raw)
    assert len(result["positions"]) == 1
    pos = result["positions"][0]
    assert pos["account_id"] is None
    assert pos["value"] == 800
