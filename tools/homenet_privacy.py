from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import yaml
except ImportError:  # pragma: no cover - operator feedback is handled by callers
    yaml = None


ROOT = Path(__file__).resolve().parents[1]

PRIVACY_ALLOW_RE = re.compile(
    r"(example\.(com|net|invalid)|REPLACE|PLACEHOLDER|change-me|password1|generated-by|00000000000000000000000000000000|<[^>]+>|xxx)",
    re.IGNORECASE,
)
PRIVACY_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    ("high", "private-key-block", re.compile(r"BEGIN (OPENSSH|RSA|EC|DSA|PRIVATE) PRIVATE KEY")),
    ("high", "cloudflare-token", re.compile(r"\bcfat_[A-Za-z0-9_-]{20,}\b")),
    ("high", "jwt-like-token", re.compile(r"\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b")),
    ("high", "proxy-subscription-url", re.compile(r"https?://[^\s\"']*(sub|subscribe|subscription|config)[^\s\"']*(token|api|key|secret)=[^\s\"']+", re.IGNORECASE)),
    ("high", "secret-env-assignment", re.compile(r"^\s*[A-Z0-9_]*(PASSWORD|PASSWD|TOKEN|SECRET|PRIVATE_KEY|SUBSCRIPTION|COOKIE|SESSION)[A-Z0-9_]*\s*=\s*['\"]?[^'\"\s#]+", re.IGNORECASE)),
    ("high", "cloudflare-account-id", re.compile(r"\bCLOUDFLARE_ACCOUNT_ID\s*=\s*['\"]?[a-f0-9]{32}\b", re.IGNORECASE)),
    ("medium", "email-address", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("medium", "mainland-phone-number", re.compile(r"\b1[3-9]\d{9}\b")),
]


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_yaml(path: Path) -> Any:
    if yaml is None:
        raise RuntimeError("PyYAML is required. Install with: pip install pyyaml")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def privacy_public_roots() -> list[Path]:
    roots = [
        ROOT / "README.md",
        ROOT / "LICENSE",
        ROOT / "CONTRIBUTING.md",
        ROOT / "SECURITY.md",
        ROOT / "PUBLISHING.md",
        ROOT / "VERSIONING.md",
        ROOT / ".gitignore",
        ROOT / ".github",
        ROOT / "homenet",
        ROOT / "tools",
        ROOT / "schemas",
        ROOT / "docs",
        ROOT / "templates",
        ROOT / "ops",
        ROOT / "instances" / "example-openwrt-pi",
        ROOT / "instances" / "example-openwrt-only",
    ]
    return [path for path in roots if path.exists()]


def privacy_skip_path(path: Path) -> bool:
    rel = path.relative_to(ROOT) if path.is_absolute() and path.is_relative_to(ROOT) else path
    parts = set(rel.parts)
    if parts & {".git", "__pycache__", "node_modules", "dist"}:
        return True
    text = str(rel)
    skip_prefixes = [
        ".env",
        "ddns-go/",
        "cloudflared/",
        "wg-easy/data/",
        "adguard/conf/AdGuardHome.yaml",
        "adguard/work/",
        "mihomo/cache.db",
        "mihomo/geoip.metadb",
        "mihomo/geosite.dat",
        "mihomo/GeoSite.dat",
        "mihomo/proxies/",
        "mihomo/ui/",
        "maintenance/state/",
        "maintenance/backups/",
        "maintenance/mihomo/mihomo-update.env",
        "apps/ops/frontend/node_modules/",
        "apps/ops/frontend/dist/",
        "apps/ops/static/",
    ]
    if any(text == item.rstrip("/") or text.startswith(item) for item in skip_prefixes):
        return True
    return path.suffix.lower() in {".pyc", ".db", ".sqlite", ".gz", ".png", ".jpg", ".jpeg", ".ico", ".dat"}


def collect_privacy_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if not path.exists() or privacy_skip_path(path):
            continue
        if path.is_file():
            files.append(path)
            continue
        for root, dirs, names in os.walk(path):
            root_path = Path(root)
            dirs[:] = [name for name in dirs if not privacy_skip_path(root_path / name)]
            for name in names:
                candidate = root_path / name
                if not privacy_skip_path(candidate) and candidate.is_file():
                    files.append(candidate)
    return sorted(set(files), key=lambda item: str(item))


def privacy_line_allowed(line: str) -> bool:
    return bool(PRIVACY_ALLOW_RE.search(line))


def is_public_placeholder_host(host: str) -> bool:
    normalized = host.strip().lower().rstrip(".")
    return normalized in {"example.com", "example.net", "example.invalid"} or normalized.endswith(
        (".example.com", ".example.net", ".example.invalid")
    )


def add_private_marker(candidates: set[str], value: Any) -> None:
    if not isinstance(value, str):
        return
    marker = value.strip()
    if len(marker) < 3:
        return
    if is_public_placeholder_host(marker):
        return
    if marker.lower() in {"openwrt", "home", "lan", "iot", "guest", "ops", "main", "room", "router", "server"}:
        return
    candidates.add(marker)


def add_private_host_marker(candidates: set[str], value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        return
    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = (parsed.hostname or "").strip().lower()
    if host and not is_public_placeholder_host(host):
        candidates.add(host)


def instance_private_patterns(instance: Path) -> list[tuple[str, str, re.Pattern[str]]]:
    if instance.name.startswith("example-"):
        return []
    candidates: set[str] = set()
    add_private_marker(candidates, instance.name)
    for local_path in [instance / "site.yaml", instance / "devices.yaml", instance / "services.yaml"]:
        try:
            data = load_yaml(local_path)
        except Exception:
            data = {}
        if not isinstance(data, dict):
            continue
        site = data.get("site") if isinstance(data.get("site"), dict) else {}
        for key in ("name", "display_name", "domain"):
            add_private_marker(candidates, site.get(key) if isinstance(site, dict) else "")
        for section_name in ("wifi", "networks"):
            section = data.get(section_name) if isinstance(data.get(section_name), dict) else {}
            for row in section.values():
                if not isinstance(row, dict):
                    continue
                for key in ("ssid", "cidr", "gateway"):
                    add_private_marker(candidates, row.get(key))
        for row in as_list(data.get("devices")):
            if not isinstance(row, dict):
                continue
            for key in ("ip", "mac"):
                add_private_marker(candidates, row.get(key))
        for entry in as_list(data.get("remote_ingress")):
            if not isinstance(entry, dict):
                continue
            for key in ("href", "name"):
                add_private_host_marker(candidates, entry.get(key))
    return [
        ("high", "private-instance-marker", re.compile(re.escape(candidate), re.IGNORECASE))
        for candidate in sorted(candidates)
    ]


def public_instance_label(instance: Path) -> str:
    try:
        rel = instance.resolve().relative_to(ROOT.resolve())
    except ValueError:
        return "private-instance"
    if rel.parts[:1] == ("instances",) and len(rel.parts) >= 2 and rel.parts[1].startswith("example-"):
        return str(rel)
    return "private-instance"


def scan_privacy_file(path: Path, *, scope: str, extra_patterns: list[tuple[str, str, re.Pattern[str]]] | None = None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return findings
    if "\0" in text:
        return findings
    rel = str(path.relative_to(ROOT)) if path.is_absolute() and path.is_relative_to(ROOT) else str(path)
    env_like_file = (
        path.suffix.lower() in {".env", ".yaml", ".yml", ".json", ".conf"}
        or "env" in path.name.lower()
        or path.name in {"Caddyfile"}
    )
    for line_no, line in enumerate(text.splitlines(), start=1):
        for severity, risk, pattern in [*PRIVACY_PATTERNS, *(extra_patterns or [])]:
            if risk == "secret-env-assignment" and not env_like_file:
                continue
            if not pattern.search(line):
                continue
            if risk not in {"private-domain", "email-address", "mainland-phone-number"} and privacy_line_allowed(line):
                continue
            if scope == "instance" and risk in {"private-domain", "email-address", "mainland-phone-number"}:
                continue
            findings.append({
                "severity": severity,
                "risk": risk,
                "path": rel,
                "line": line_no,
                "detail": "Potential private value found. Matched content is intentionally suppressed.",
            })
            break
    return findings


def build_privacy_report(instance: Path, *, scope: str = "public") -> dict[str, Any]:
    if scope not in {"public", "instance", "all"}:
        raise ValueError(f"unsupported privacy scope: {scope}")
    roots: list[Path] = []
    if scope in {"public", "all"}:
        roots.extend(privacy_public_roots())
    if scope in {"instance", "all"}:
        roots.extend([instance / "site.yaml", instance / "devices.yaml", instance / "services.yaml", instance / "README.md"])
    files = collect_privacy_files(roots)
    extra_patterns = instance_private_patterns(instance)
    findings: list[dict[str, Any]] = []
    for path in files:
        findings.extend(scan_privacy_file(path, scope="instance" if path.is_relative_to(instance) else "public", extra_patterns=extra_patterns))
    by_severity: dict[str, int] = {}
    by_risk: dict[str, int] = {}
    for finding in findings:
        severity = str(finding.get("severity") or "unknown")
        risk = str(finding.get("risk") or "unknown")
        by_severity[severity] = by_severity.get(severity, 0) + 1
        by_risk[risk] = by_risk.get(risk, 0) + 1
    return {
        "schema": "homenet.privacy.v1",
        "scope": scope,
        "instance": public_instance_label(instance),
        "read_only": True,
        "prints_matched_values": False,
        "ok": not findings,
        "summary": {
            "files_scanned": len(files),
            "findings": len(findings),
            "high": by_severity.get("high", 0),
            "medium": by_severity.get("medium", 0),
        },
        "by_severity": dict(sorted(by_severity.items())),
        "by_risk": dict(sorted(by_risk.items())),
        "findings": findings,
        "ignored": [
            "Known placeholders such as example.invalid, REPLACE_WITH_*, change-me, password1, generated-by, and angle-bracket placeholders.",
            "Runtime/private storage paths such as .env, wg-easy data, AdGuardHome.yaml, Mihomo caches/proxies, ddns-go config, and maintenance/state.",
        ],
        "privacy": {
            "secrets_included": False,
            "note": "Findings include only path, line, severity, and risk type. Matched values are never printed.",
        },
    }


def print_privacy_markdown(report: dict[str, Any]) -> None:
    print("# Privacy Audit")
    print()
    print(f"- schema: `{report.get('schema')}`")
    print(f"- scope: `{report.get('scope')}`")
    print(f"- read only: {report.get('read_only')}")
    print(f"- prints matched values: {report.get('prints_matched_values')}")
    print(f"- ok: {report.get('ok')}")
    print()
    print("## Summary")
    print()
    for key, value in report.get("summary", {}).items():
        print(f"- {key}: {value}")
    print()
    if report.get("findings"):
        print("## Findings")
        print()
        print("| Severity | Risk | Path | Line |")
        print("| --- | --- | --- | --- |")
        for finding in report.get("findings", []):
            if isinstance(finding, dict):
                print(
                    f"| {finding.get('severity', '')} | {finding.get('risk', '')} | "
                    f"`{finding.get('path', '')}` | {finding.get('line', '')} |"
                )
        print()
    print("## Ignored")
    print()
    for item in report.get("ignored", []):
        print(f"- {item}")
    print()
