# Changelog

All notable changes to this project will be documented in this file.

## [0.1.1] - 2026-05-06

### Fixed
- Config flow failed to load with `500 Internal Server Error` on Home Assistant 2024.12 and newer because the options flow assigned to `OptionsFlow.config_entry`, which is now a read-only property. The entry is now stored under a private attribute.
- Replaced `SelectOptionDict(...)` constructor calls with plain dicts so the selector schema also builds on older HA releases that don't expose the typed-dict helper.

## [0.1.0] - 2026-05-06

### Added
- Configurable polling interval (5, 15, or 60 minutes) selectable during setup and editable afterwards via the integration's *Configure* options flow.

### Changed
- Default polling interval is now **5 minutes** (previously 15).
- Positions whose current value is 0 are no longer registered as sensors when first seen, avoiding clutter from sold-out or empty holdings. Sensors that already exist are kept — they simply report 0 — so history and statistics are preserved.

## [0.0.2] - 2026-05-06

### Fixed
- Total portfolio value sensor reported `USD` regardless of the user's actual base currency. The integration now reads the base currency from `/api/v1/user` (`settings.baseCurrency`) so the unit matches what Ghostfolio shows in its UI.

## [0.0.1] - 2026-05-05

### Added
- Initial release of the Ghostfolio integration for Home Assistant.
- Authenticates against a Ghostfolio instance using an access token.
- `sensor.ghostfolio_total_portfolio_value` – total portfolio value in the configured base currency, updated every 15 minutes.
- One sensor per `(account, position)` pair with market value as state and quantity, market price, and asset class as attributes.
- Config flow for setup via the Home Assistant UI (URL, access token, optional SSL verification toggle).
- HACS-compatible packaging.
- GitHub Actions CI: HACS validation, `hassfest`, unit tests, and a full integration test that boots a real Ghostfolio instance alongside Home Assistant.
