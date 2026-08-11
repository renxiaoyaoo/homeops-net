from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    try:
        text = path.read_text()
    except OSError:
        return values
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def load_cloudflare_secret_names(env_path: Path = Path("/home/pi/.config/secrets/cloudflare.env")) -> tuple[dict[str, str], list[str]]:
    keys = ["CLOUDFLARE_ACCOUNT_ID", "CF_ZERO_TRUST_API_TOKEN"]
    values = {key: os.environ.get(key, "") for key in keys}
    local_values = read_env_file(env_path)
    for key in keys:
        if not values.get(key):
            values[key] = local_values.get(key, "")
    missing = [key for key in keys if not values.get(key)]
    return values, missing


def cloudflare_api_get(account_id: str, token: str, path: str, timeout: int = 12) -> tuple[dict[str, Any] | None, str | None]:
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}{path}"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        return None, exc.__class__.__name__


def check_cloudflare_provider_live(
    evidence: dict[str, Any],
    reporter: Any,
    as_list: Callable[[Any], list[Any]],
) -> tuple[int, int]:
    checks = [
        check
        for check in evidence.get("checks", [])
        if isinstance(check, dict) and check.get("group") == "Cloudflare provider"
    ]
    if not checks:
        return 0, 0

    secrets, missing = load_cloudflare_secret_names()
    if missing:
        reporter.warn("live", f"Cloudflare provider checks skipped; missing local secret name(s): {', '.join(missing)}")
        return 0, len(checks)

    account_id = secrets["CLOUDFLARE_ACCOUNT_ID"]
    token = secrets["CF_ZERO_TRUST_API_TOKEN"]
    executed = 0
    skipped = 0
    tunnels_cache: dict[str, Any] | None = None
    tunnels_error: str | None = None
    apps_cache: dict[str, Any] | None = None
    apps_error: str | None = None

    for check in checks:
        check_id = str(check.get("id") or "")
        if check_id == "cloudflare-tunnels-list":
            executed += 1
            if tunnels_cache is None and tunnels_error is None:
                tunnels_cache, tunnels_error = cloudflare_api_get(account_id, token, "/tunnels")
            if tunnels_error:
                reporter.warn("live", f"Cloudflare Tunnel API unavailable: {tunnels_error}")
                continue
            result = tunnels_cache.get("result") if isinstance(tunnels_cache, dict) else None
            tunnels = result if isinstance(result, list) else []
            statuses: dict[str, int] = {}
            for tunnel in tunnels:
                if not isinstance(tunnel, dict):
                    continue
                status = str(tunnel.get("status") or "unknown")
                statuses[status] = statuses.get(status, 0) + 1
            healthy = statuses.get("healthy", 0) + statuses.get("degraded", 0)
            if healthy:
                summary = ", ".join(f"{name}={count}" for name, count in sorted(statuses.items()))
                reporter.ok("live", f"Cloudflare Tunnel API readable; active tunnel status count: {summary}")
            elif tunnels:
                summary = ", ".join(f"{name}={count}" for name, count in sorted(statuses.items()))
                reporter.warn("live", f"Cloudflare Tunnel API readable but no healthy/degraded tunnel: {summary}")
            else:
                reporter.warn("live", "Cloudflare Tunnel API readable but returned no tunnels")
        elif check_id == "cloudflare-access-apps-list":
            executed += 1
            if apps_cache is None and apps_error is None:
                apps_cache, apps_error = cloudflare_api_get(account_id, token, "/access/apps")
            if apps_error:
                reporter.warn("live", f"Cloudflare Access apps API unavailable: {apps_error}")
                continue
            result = apps_cache.get("result") if isinstance(apps_cache, dict) else None
            apps = result if isinstance(result, list) else []
            domains: set[str] = set()
            for app in apps:
                if not isinstance(app, dict):
                    continue
                domain = app.get("domain")
                if isinstance(domain, str) and domain:
                    domains.add(domain.lower())
                for key in ["self_hosted_domains", "cors_headers"]:
                    value = app.get(key)
                    if isinstance(value, list):
                        domains.update(str(item).lower() for item in value if isinstance(item, str) and item)
            expected = [str(item).lower() for item in as_list(check.get("expected_hostnames")) if str(item).strip()]
            missing_hosts = sorted(host for host in expected if host not in domains)
            if expected and not missing_hosts:
                reporter.ok("live", f"Cloudflare Access apps API readable; declared app hostname(s) present: {len(expected)}")
            elif expected:
                reporter.warn("live", f"Cloudflare Access apps API readable; missing declared hostname(s): {', '.join(missing_hosts)}")
            else:
                reporter.ok("live", f"Cloudflare Access apps API readable; app count={len(apps)}")
        else:
            skipped += 1
            reporter.warn("live", f"Cloudflare provider check {check_id or 'unknown'} has no executor")
    return executed, skipped
