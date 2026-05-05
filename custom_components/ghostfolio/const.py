"""Constants for the Ghostfolio integration."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "ghostfolio"

CONF_URL = "url"
CONF_ACCESS_TOKEN = "access_token"
CONF_VERIFY_SSL = "verify_ssl"

DEFAULT_URL = "https://ghostfol.io"
DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)

ATTR_ACCOUNT_ID = "account_id"
ATTR_ACCOUNT_NAME = "account_name"
ATTR_SYMBOL = "symbol"
ATTR_NAME = "name"
ATTR_QUANTITY = "quantity"
ATTR_MARKET_PRICE = "market_price"
ATTR_CURRENCY = "currency"
ATTR_DATA_SOURCE = "data_source"
ATTR_ASSET_CLASS = "asset_class"
