# Ghostfolio for Home Assistant

A custom [HACS](https://hacs.xyz/) integration that exposes data from a
[Ghostfolio](https://ghostfol.io) instance as Home Assistant sensors.

## What it does

- Authenticates against a Ghostfolio instance using your **security / access
  token** (the one shown when your user was created, or available via *My
  Ghostfolio → Account → Security token*).
- Polls `/api/v1/portfolio/details` on a configurable interval (5, 15, or 60
  minutes; default **5**). The interval can be changed at any time from
  *Settings → Devices & Services → Ghostfolio → Configure*.
- Creates the following entities:
  - **`sensor.ghostfolio_total_portfolio_value`** – total portfolio value in
    your base currency.
  - **One sensor per `(account, position)` pair** – named
    `<Account name> <SYMBOL>`, with the position's market value as its state
    and additional attributes (quantity, market price, asset class, etc.).

Self-hosted and `https://ghostfol.io` instances are both supported.

## Installation

### Via HACS (recommended)

1. In Home Assistant, open **HACS → Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/lvlie/ha-ghostfolio` as an **Integration**.
3. Install the *Ghostfolio* integration and restart Home Assistant.
4. Go to **Settings → Devices & Services → Add Integration** and pick
   *Ghostfolio*.

### Manual

Copy `custom_components/ghostfolio` into your Home Assistant
`config/custom_components/` directory, restart, and add the integration from
the UI.

## Configuration

| Field | Description |
| --- | --- |
| URL | Base URL of your Ghostfolio instance, e.g. `https://ghostfol.io` or `http://homeassistant.local:3333` |
| Access token | The security token shown in *Account → Security token* |
| Verify SSL | Disable for self-signed certificates |
| Update interval | How often to poll Ghostfolio: 5, 15, or 60 minutes |

## Development & CI

A GitHub Actions workflow (`.github/workflows/test.yml`) spins up a real
Ghostfolio instance (Postgres + Redis + Ghostfolio) inside the runner, creates
a user via the API, then boots Home Assistant with this integration loaded
against that instance. The job fails if any errors are written to the
Home Assistant log.

The same workflow can also point at `https://ghostfol.io` for smoke tests, but
because the public demo doesn't expose API tokens, the local docker-compose
path is the source of truth.
