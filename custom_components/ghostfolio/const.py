"""Constants for the Ghostfolio integration."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "ghostfolio"

CONF_URL = "url"
CONF_ACCESS_TOKEN = "access_token"
CONF_VERIFY_SSL = "verify_ssl"
CONF_SCAN_INTERVAL_MINUTES = "scan_interval_minutes"

DEFAULT_URL = "https://ghostfol.io"
DEFAULT_SCAN_INTERVAL_MINUTES = 5
SCAN_INTERVAL_OPTIONS = (5, 15, 60)
DEFAULT_SCAN_INTERVAL = timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES)

ATTR_ACCOUNT_ID = "account_id"
ATTR_ACCOUNT_NAME = "account_name"
ATTR_SYMBOL = "symbol"
ATTR_NAME = "name"
ATTR_QUANTITY = "quantity"
ATTR_MARKET_PRICE = "market_price"
ATTR_CURRENCY = "currency"
ATTR_DATA_SOURCE = "data_source"
ATTR_ASSET_CLASS = "asset_class"
