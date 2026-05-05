"""Create a user, an account, and a few activities in a fresh Ghostfolio instance.

Used by the GitHub Actions workflow to give the integration something
realistic to read.

Usage:
    python bootstrap_ghostfolio.py --url http://localhost:3333 --output env
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any


def _request(
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
    if not raw:
        return {}
    return json.loads(raw)


def wait_for_health(url: str, retries: int = 60) -> None:
    health = f"{url.rstrip('/')}/api/v1/health"
    for attempt in range(retries):
        try:
            urllib.request.urlopen(health, timeout=5).read()
            return
        except (urllib.error.URLError, urllib.error.HTTPError):
            time.sleep(2)
    raise SystemExit(f"Ghostfolio at {health} did not become healthy")


def create_user(url: str) -> dict[str, Any]:
    """POST /api/v1/user — first user becomes admin and gets an access token."""
    return _request("POST", f"{url}/api/v1/user")


def login_anonymous(url: str, access_token: str) -> str:
    resp = _request(
        "POST",
        f"{url}/api/v1/auth/anonymous",
        body={"accessToken": access_token},
    )
    auth_token = resp.get("authToken")
    if not auth_token:
        raise SystemExit(f"No authToken returned: {resp}")
    return auth_token


def create_account(url: str, jwt: str, name: str, currency: str) -> dict[str, Any]:
    return _request(
        "POST",
        f"{url}/api/v1/account",
        body={
            "balance": 0,
            "comment": None,
            "currency": currency,
            "isExcluded": False,
            "name": name,
            "platformId": None,
        },
        token=jwt,
    )


def import_activities(url: str, jwt: str, activities: list[dict[str, Any]]) -> None:
    try:
        _request(
            "POST",
            f"{url}/api/v1/import",
            body={"activities": activities},
            token=jwt,
        )
    except urllib.error.HTTPError as err:
        # Importing may fail if the data source is unavailable in CI; we don't
        # want that to bring the whole pipeline down because the integration is
        # still expected to handle empty portfolios gracefully.
        body = err.read().decode("utf-8", errors="ignore")
        print(f"WARN: activity import failed ({err.code}): {body}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", required=True, help="Path to write env vars to")
    args = parser.parse_args()

    wait_for_health(args.url)

    user = create_user(args.url)
    access_token = user.get("accessToken")
    if not access_token:
        raise SystemExit(f"User creation did not return an access token: {user}")
    print(f"Created user with access token: {access_token[:6]}…")

    jwt = login_anonymous(args.url, access_token)

    accounts = [
        ("CI Brokerage", "USD"),
        ("CI Crypto", "USD"),
    ]
    created_accounts = []
    for name, currency in accounts:
        try:
            acc = create_account(args.url, jwt, name, currency)
            created_accounts.append(acc)
            print(f"Created account {name}: {acc.get('id')}")
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8", errors="ignore")
            print(f"WARN: account creation failed ({err.code}): {body}", file=sys.stderr)

    if created_accounts:
        first = created_accounts[0]
        activities = [
            {
                "accountId": first.get("id"),
                "currency": "USD",
                "dataSource": "MANUAL",
                "date": "2024-01-15T00:00:00.000Z",
                "fee": 0,
                "quantity": 10,
                "symbol": "DEMO",
                "type": "BUY",
                "unitPrice": 100,
            }
        ]
        import_activities(args.url, jwt, activities)

    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(f"GHOSTFOLIO_TOKEN={access_token}\n")
    print(f"Wrote credentials to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
