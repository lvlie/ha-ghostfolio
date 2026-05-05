# Changelog

All notable changes to this project will be documented in this file.

## [0.0.1] - 2026-05-05

### Added
- Initial release of the Ghostfolio integration for Home Assistant.
- Authenticates against a Ghostfolio instance using an access token.
- `sensor.ghostfolio_total_portfolio_value` – total portfolio value in the configured base currency, updated every 15 minutes.
- One sensor per `(account, position)` pair with market value as state and quantity, market price, and asset class as attributes.
- Config flow for setup via the Home Assistant UI (URL, access token, optional SSL verification toggle).
- HACS-compatible packaging.
- GitHub Actions CI: HACS validation, `hassfest`, unit tests, and a full integration test that boots a real Ghostfolio instance alongside Home Assistant.
