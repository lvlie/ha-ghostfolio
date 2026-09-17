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

## Requirements

- Home Assistant **2025.2.0** or newer.
- A Ghostfolio instance reachable from Home Assistant.

If Ghostfolio stops accepting the stored token, Home Assistant raises a repair
notification and the integration asks for a new one through its
reauthentication flow — the entry does not need to be removed and re-added.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
pip install pre-commit && pre-commit install

pytest                       # unit tests against the Home Assistant test harness
pre-commit run --all-files   # ruff lint + format, JSON/YAML checks, codespell
```

`requirements_test.txt` pins `pytest-homeassistant-custom-component`, which in
turn pins the exact Home Assistant version everything is tested against.
Dependabot raises a PR when a newer one is available, which is how this
integration finds out about breaking core changes.

## CI

| Workflow | Job | What it does |
| --- | --- | --- |
| `validate.yml` | `hassfest` | Home Assistant's own integration manifest/strings validation |
| `validate.yml` | `hacs` | HACS repository validation |
| `test.yml` | `lint` | Runs every pre-commit hook |
| `test.yml` | `unit` | `pytest` with coverage, using `pytest-homeassistant-custom-component` |
| `test.yml` | `integration-test` | Boots Postgres + Redis + Ghostfolio in Docker, creates a user with positions over the API, then starts a real Home Assistant with this integration pointed at it and fails if the log contains errors |

`validate.yml` also runs weekly on a schedule, because hassfest and HACS rules
change independently of this repository.
