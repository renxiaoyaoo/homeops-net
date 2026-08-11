from __future__ import annotations

import datetime
import ipaddress
import shutil
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

def monitor_group(category: str, scope: str) -> str:
    if scope == "remote":
        return "Remote Access"
    return {
        "gateway": "Network Core",
        "network-core": "Network Core",
        "remote-entry": "Remote Access",
        "udp-entry": "Remote Access",
        "external": "Remote Access",
        "home-core": "Home Core",
        "control-core": "HomeNet Core",
        "storage": "Home Core",
        "system-task": "HomeNet Core",
    }.get(category, "Other")


def build_kuma_export(metadata: dict[str, Any]) -> dict[str, Any]:
    services_by_id = {
        str(service.get("id")): service
        for service in metadata.get("service_directory", [])
        if isinstance(service, dict) and service.get("id")
    }
    monitors: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    def add_monitor(row: dict[str, Any], source: str) -> None:
        service_id = str(row.get("service_id") or "")
        service = services_by_id.get(service_id, {})
        monitor_type = str(row.get("monitor_type") or "external")
        target = str(row.get("target") or "")
        key = (service_id, monitor_type, target)
        if not target or key in seen:
            return
        seen.add(key)
        scope = str(row.get("scope") or "")
        auto_importable = monitor_type in {"http", "tcp", "ping", "dns"}
        monitors.append({
            "name": row.get("name") or service.get("name") or service_id or target,
            "type": monitor_type,
            "target": target,
            "service_id": service_id,
            "scope": scope,
            "group": monitor_group(str(service.get("category") or ""), scope),
            "source": source,
            "auto_importable": auto_importable,
            "recommended_interval_seconds": 60 if scope == "remote" else 120,
            "alert": scope in {"remote", "LAN/WAN", "WAN"} or monitor_type in {"http", "tcp"},
        })

    for row in metadata.get("kuma_inventory", []):
        if isinstance(row, dict):
            add_monitor(row, str(row.get("source") or "metadata.kuma_inventory"))

    for entry in metadata.get("remote_ingress", []):
        if not isinstance(entry, dict):
            continue
        href = str(entry.get("href") or "")
        kind = str(entry.get("kind") or "external")
        scheme = urlparse(href).scheme.lower() if href else ""
        if scheme in {"http", "https"}:
            monitor_type = "http"
            target = href
        elif kind == "wireguard-udp":
            monitor_type = "udp"
            service = services_by_id.get(str(entry.get("service_id") or ""), {})
            target = str(service.get("remote_url") or entry.get("name") or entry.get("target") or "")
        else:
            monitor_type = kind
            target = href or str(entry.get("target") or "")
        add_monitor({
            "name": entry.get("name") or entry.get("id"),
            "monitor_type": monitor_type,
            "target": target,
            "service_id": entry.get("service_id") or "",
            "scope": "remote",
        }, "metadata.remote_ingress")

    monitors = sorted(monitors, key=lambda item: (str(item.get("group")), str(item.get("name")), str(item.get("target"))))
    return {
        "schema": "homenet.kuma_inventory.v1",
        "instance": metadata.get("instance") or {},
        "generated_from": metadata.get("schema"),
        "monitor_count": len(monitors),
        "auto_importable_count": sum(1 for monitor in monitors if monitor.get("auto_importable")),
        "groups": sorted({str(monitor.get("group")) for monitor in monitors if monitor.get("group")}),
        "monitors": monitors,
        "apply": {
            "read_only": True,
            "status": "not_implemented",
            "message": "This command only exports monitor candidates. It does not write to Uptime Kuma.",
        },
    }


def normalize_kuma_type(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"port", "tcp"}:
        return "tcp"
    if raw in {"keyword", "json-query", "real-browser"}:
        return "http"
    return raw


def normalize_host_alias(host: str, host_aliases: dict[str, str] | None = None) -> str:
    lowered = host.strip().lower()
    aliases = host_aliases or {}
    return aliases.get(lowered, lowered)


def normalize_monitor_target(monitor_type: Any, target: Any, host_aliases: dict[str, str] | None = None) -> str:
    kind = normalize_kuma_type(monitor_type)
    raw = str(target or "").strip()
    if kind == "http":
        parsed = urlparse(raw)
        if parsed.scheme and parsed.netloc:
            scheme = parsed.scheme.lower()
            host = normalize_host_alias(parsed.hostname or "", host_aliases)
            port = f":{parsed.port}" if parsed.port else ""
            netloc = f"{host}{port}"
            path = parsed.path or "/"
            if path != "/" and path.endswith("/"):
                path = path.rstrip("/")
            query = f"?{parsed.query}" if parsed.query else ""
            return f"{scheme}://{netloc}{path}{query}"
    if kind in {"tcp", "dns"} and ":" in raw:
        host, _, port = raw.rpartition(":")
        if host and port:
            return f"{normalize_host_alias(host, host_aliases)}:{port}".lower()
    if kind == "ping":
        return normalize_host_alias(raw, host_aliases)
    return raw.lower()


def kuma_monitor_target(row: dict[str, Any]) -> str:
    monitor_type = normalize_kuma_type(row.get("type"))
    if monitor_type == "http":
        return str(row.get("url") or "")
    if monitor_type == "tcp":
        host = str(row.get("hostname") or "").strip()
        port = str(row.get("port") or "").strip()
        return f"{host}:{port}" if host and port else host
    if monitor_type == "ping":
        return str(row.get("hostname") or row.get("url") or "")
    if monitor_type == "dns":
        host = str(row.get("hostname") or "").strip()
        port = str(row.get("port") or "53").strip()
        return f"{host}:{port}" if host else ""
    return str(row.get("url") or row.get("hostname") or "")


def kuma_monitor_key(monitor_type: Any, target: Any, host_aliases: dict[str, str] | None = None) -> str:
    return f"{normalize_kuma_type(monitor_type)} {normalize_monitor_target(monitor_type, target, host_aliases)}"


def read_kuma_monitors(db_path: Path) -> list[dict[str, Any]]:
    uri = f"file:{db_path}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        columns = [row[1] for row in conn.execute("pragma table_info(monitor)")]
        required = {"id", "name", "type", "url", "hostname", "port", "active", "parent", "interval", "retry_interval", "maxretries", "description", "conditions"}
        selected = [column for column in columns if column in required]
        if not {"id", "name", "type"}.issubset(set(selected)):
            raise RuntimeError("Kuma monitor table is missing required columns")
        rows = conn.execute(f"select {','.join(selected)} from monitor order by id").fetchall()
    finally:
        conn.close()

    monitors: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        target = kuma_monitor_target(item)
        item["normalized_type"] = normalize_kuma_type(item.get("type"))
        item["target"] = target
        item["key"] = kuma_monitor_key(item.get("type"), target)
        monitors.append(item)
    return monitors


def infer_kuma_host_aliases(export: dict[str, Any]) -> dict[str, str]:
    counts: dict[str, int] = {}
    for monitor in export.get("monitors", []):
        if not isinstance(monitor, dict):
            continue
        target = str(monitor.get("target") or "")
        parsed = urlparse(target)
        host = parsed.hostname or ""
        if not host and ":" in target:
            host = target.rpartition(":")[0]
        if not host:
            continue
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            continue
        if not ip.is_private or host.endswith(".1") or host.endswith(".2"):
            continue
        counts[host] = counts.get(host, 0) + 1
    service_host = max(counts.items(), key=lambda item: item[1])[0] if counts else ""
    if not service_host:
        return {}
    return {
        "localhost": service_host,
        "127.0.0.1": service_host,
        "::1": service_host,
    }


def build_kuma_diff(export: dict[str, Any], db_path: Path) -> dict[str, Any]:
    expected_all = [m for m in export.get("monitors", []) if isinstance(m, dict)]
    expected = [m for m in expected_all if m.get("auto_importable")]
    manual = [m for m in expected_all if not m.get("auto_importable")]
    actual = read_kuma_monitors(db_path)
    host_aliases = infer_kuma_host_aliases(export)

    actual_by_key: dict[str, list[dict[str, Any]]] = {}
    actual_by_name: dict[str, list[dict[str, Any]]] = {}
    for monitor in actual:
        key = kuma_monitor_key(monitor.get("type"), monitor.get("target"), host_aliases)
        actual_by_key.setdefault(key, []).append(monitor)
        actual_by_name.setdefault(str(monitor.get("name") or "").strip().lower(), []).append(monitor)

    matched: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    interval_drift: list[dict[str, Any]] = []
    matched_actual_ids: set[int] = set()

    for monitor in expected:
        expected_type = normalize_kuma_type(monitor.get("type"))
        expected_target = str(monitor.get("target") or "")
        key = kuma_monitor_key(expected_type, expected_target, host_aliases)
        candidates = actual_by_key.get(key, [])
        match_type = "target"
        if not candidates:
            name_key = str(monitor.get("name") or "").strip().lower()
            candidates = actual_by_name.get(name_key, [])
            match_type = "name" if candidates else ""
        if not candidates:
            missing.append({
                "name": monitor.get("name") or "",
                "type": expected_type,
                "target": expected_target,
                "group": monitor.get("group") or "",
                "source": monitor.get("source") or "",
            })
            continue

        actual_monitor = candidates[0]
        actual_id = actual_monitor.get("id")
        if isinstance(actual_id, int):
            matched_actual_ids.add(actual_id)
        expected_interval = monitor.get("recommended_interval_seconds")
        differences: list[str] = []
        if normalize_kuma_type(actual_monitor.get("type")) != expected_type:
            differences.append("type")
        if normalize_monitor_target(actual_monitor.get("type"), actual_monitor.get("target"), host_aliases) != normalize_monitor_target(expected_type, expected_target, host_aliases):
            differences.append("target")
        if expected_interval and actual_monitor.get("interval") and int(actual_monitor.get("interval") or 0) != int(expected_interval):
            interval_drift.append({
                "expected_name": monitor.get("name") or "",
                "actual_id": actual_monitor.get("id"),
                "actual_name": actual_monitor.get("name") or "",
                "expected_interval": expected_interval,
                "actual_interval": actual_monitor.get("interval"),
            })
        row = {
            "expected_name": monitor.get("name") or "",
            "actual_id": actual_monitor.get("id"),
            "actual_name": actual_monitor.get("name") or "",
            "type": expected_type,
            "target": expected_target,
            "actual_type": normalize_kuma_type(actual_monitor.get("type")),
            "actual_target": actual_monitor.get("target") or "",
            "match": match_type,
        }
        if differences:
            row["differences"] = differences
            changed.append(row)
        else:
            matched.append(row)

    extra: list[dict[str, Any]] = []
    for monitor in actual:
        monitor_id = monitor.get("id")
        if isinstance(monitor_id, int) and monitor_id in matched_actual_ids:
            continue
        extra.append({
            "id": monitor.get("id"),
            "name": monitor.get("name") or "",
            "type": normalize_kuma_type(monitor.get("type")),
            "target": monitor.get("target") or "",
            "active": bool(monitor.get("active")),
            "parent": monitor.get("parent"),
        })

    return {
        "schema": "homenet.kuma_diff.v1",
        "instance": export.get("instance") or {},
        "db_path": str(db_path),
        "expected_count": len(expected),
        "manual_count": len(manual),
        "actual_count": len(actual),
        "matched_count": len(matched),
        "changed_count": len(changed),
        "missing_count": len(missing),
        "extra_count": len(extra),
        "interval_drift_count": len(interval_drift),
        "host_aliases": host_aliases,
        "matched": matched,
        "changed": changed,
        "interval_drift": interval_drift,
        "missing": missing,
        "extra": extra,
        "manual_candidates": [
            {
                "name": monitor.get("name") or "",
                "type": monitor.get("type") or "",
                "target": monitor.get("target") or "",
                "reason": "manual or unsupported by automatic import",
            }
            for monitor in manual
        ],
        "apply": {
            "read_only": True,
            "message": "Diff reads Uptime Kuma SQLite with immutable=1 and does not write monitors.",
        },
    }


def build_kuma_import_plan(diff: dict[str, Any]) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    for item in diff.get("missing", []):
        actions.append({
            "action": "create-monitor",
            "mode": "proposed",
            "name": item.get("name") or "",
            "type": item.get("type") or "",
            "target": item.get("target") or "",
            "group": item.get("group") or "",
            "reason": "Declared by instance but not found in Uptime Kuma.",
        })
    for item in diff.get("changed", []):
        actions.append({
            "action": "update-monitor",
            "mode": "requires-review",
            "actual_id": item.get("actual_id"),
            "actual_name": item.get("actual_name") or "",
            "expected_name": item.get("expected_name") or "",
            "type": item.get("type") or "",
            "target": item.get("target") or "",
            "differences": item.get("differences") or [],
            "reason": "Monitor name matched but type/target differs from instance declaration.",
        })
    for item in diff.get("interval_drift", []):
        actions.append({
            "action": "update-interval",
            "mode": "optional",
            "actual_id": item.get("actual_id"),
            "actual_name": item.get("actual_name") or "",
            "expected_name": item.get("expected_name") or "",
            "expected_interval": item.get("expected_interval"),
            "actual_interval": item.get("actual_interval"),
            "reason": "Interval differs from recommendation. This is intentionally optional.",
        })
    for item in diff.get("extra", []):
        actions.append({
            "action": "adopt-or-ignore",
            "mode": "ignored-by-default",
            "actual_id": item.get("id"),
            "actual_name": item.get("name") or "",
            "type": item.get("type") or "",
            "target": item.get("target") or "",
            "active": item.get("active"),
            "reason": "Existing Kuma monitor is not declared by instance. Treat as operator-owned unless explicitly adopted.",
        })
    for item in diff.get("manual_candidates", []):
        actions.append({
            "action": "manual-monitor",
            "mode": "manual",
            "name": item.get("name") or "",
            "type": item.get("type") or "",
            "target": item.get("target") or "",
            "reason": item.get("reason") or "Unsupported by automatic import.",
        })

    by_mode: dict[str, int] = {}
    for action in actions:
        mode = str(action.get("mode") or "unknown")
        by_mode[mode] = by_mode.get(mode, 0) + 1

    db_path = str(diff.get("db_path") or "")
    backup_command = ""
    if db_path:
        backup_command = f"cp -p {db_path} {db_path}.homenet-backup-$(date +%Y%m%d-%H%M%S)"

    return {
        "schema": "homenet.kuma_import_plan.v1",
        "instance": diff.get("instance") or {},
        "generated_from": diff.get("schema"),
        "db_path": db_path,
        "read_only": True,
        "backup_required": True,
        "backup_command": backup_command,
        "summary": {
            "actions": len(actions),
            "by_mode": by_mode,
            "creates": sum(1 for action in actions if action.get("action") == "create-monitor"),
            "updates": sum(1 for action in actions if action.get("action") == "update-monitor"),
            "optional_interval_updates": sum(1 for action in actions if action.get("action") == "update-interval"),
            "operator_owned_extras": sum(1 for action in actions if action.get("action") == "adopt-or-ignore"),
            "manual": sum(1 for action in actions if action.get("action") == "manual-monitor"),
        },
        "safety": {
            "writes_database": False,
            "deletes_monitors": False,
            "updates_extra_monitors": False,
            "requires_diff_review": True,
            "message": "This is a plan only. A future apply command must backup the DB and require explicit confirmation before writes.",
        },
        "actions": actions,
    }


def kuma_db_type(monitor_type: Any) -> str:
    kind = normalize_kuma_type(monitor_type)
    if kind == "tcp":
        return "port"
    return kind


def split_host_port(target: str, default_port: int | None = None) -> tuple[str, int | None]:
    raw = str(target or "").strip()
    if not raw:
        return "", default_port
    parsed = urlparse(raw)
    if parsed.scheme and parsed.hostname:
        return parsed.hostname, parsed.port or default_port
    host, sep, port_text = raw.rpartition(":")
    if sep and host and port_text.isdigit():
        return host, int(port_text)
    return raw, default_port


def kuma_monitor_values(action: dict[str, Any], columns: set[str]) -> dict[str, Any]:
    kind = normalize_kuma_type(action.get("type"))
    target = str(action.get("target") or "")
    values: dict[str, Any] = {
        "name": str(action.get("name") or action.get("expected_name") or action.get("actual_name") or target),
        "type": kuma_db_type(kind),
        "active": 1,
        "interval": int(action.get("expected_interval") or 120),
        "retry_interval": 60,
        "maxretries": 3,
        "description": "Managed by HomeNet import workflow.",
    }
    if kind == "http":
        values["url"] = target
    elif kind == "tcp":
        host, port = split_host_port(target)
        values["url"] = "https://"
        values["hostname"] = host
        if port is not None:
            values["port"] = port
    elif kind == "ping":
        values["url"] = "https://"
        values["hostname"] = target
    elif kind == "dns":
        host, port = split_host_port(target, 53)
        values["url"] = "https://"
        values["hostname"] = host
        values["port"] = port or 53
        values["dns_resolve_type"] = "A"
    else:
        raise ValueError(f"unsupported Kuma monitor type for apply: {kind}")
    return {key: value for key, value in values.items() if key in columns}


def backup_kuma_db(db_path: Path) -> Path:
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = db_path.with_name(f"{db_path.name}.homenet-backup-{timestamp}")
    shutil.copy2(db_path, backup_path)
    return backup_path


def apply_kuma_import_plan(
    plan: dict[str, Any],
    *,
    confirm: str,
    include_interval_updates: bool = False,
    include_review_updates: bool = False,
) -> dict[str, Any]:
    db_path = Path(str(plan.get("db_path") or ""))
    confirmed = confirm == "APPLY-KUMA"
    actions = [action for action in plan.get("actions", []) if isinstance(action, dict)]
    creates = [action for action in actions if action.get("action") == "create-monitor"]
    intervals = [action for action in actions if action.get("action") == "update-interval"]
    review_updates = [action for action in actions if action.get("action") == "update-monitor"]
    selected: list[dict[str, Any]] = []
    selected.extend(creates)
    if include_interval_updates:
        selected.extend(intervals)
    if include_review_updates:
        selected.extend(review_updates)

    result: dict[str, Any] = {
        "schema": "homenet.kuma_apply_result.v1",
        "generated_from": plan.get("schema"),
        "instance": plan.get("instance") or {},
        "db_path": str(db_path),
        "confirmed": confirmed,
        "dry_run": not confirmed,
        "backup_path": "",
        "summary": {
            "selected": len(selected),
            "created": 0,
            "interval_updated": 0,
            "review_updated": 0,
            "ignored": len(actions) - len(selected),
            "unsupported": 0,
        },
        "safety": {
            "backup_created": False,
            "deletes_monitors": False,
            "updates_extra_monitors": False,
            "requires_confirmation": True,
            "confirmation_value": "APPLY-KUMA",
        },
        "actions": [],
    }
    if not db_path:
        result["error"] = "missing db_path"
        return result
    if not db_path.exists():
        result["error"] = f"database does not exist: {db_path}"
        return result

    conn: sqlite3.Connection | None = None
    try:
        if confirmed:
            backup_path = backup_kuma_db(db_path)
            result["backup_path"] = str(backup_path)
            result["safety"]["backup_created"] = True
        if confirmed:
            conn = sqlite3.connect(db_path)
        else:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True)
        conn.row_factory = sqlite3.Row
        columns = {row[1] for row in conn.execute("pragma table_info(monitor)").fetchall()}
        if not {"id", "name", "type"}.issubset(columns):
            raise RuntimeError("Kuma monitor table is missing required columns")

        with conn:
            for action in selected:
                action_type = str(action.get("action") or "")
                row: dict[str, Any] = {
                    "action": action_type,
                    "name": action.get("name") or action.get("expected_name") or action.get("actual_name") or "",
                    "target": action.get("target") or "",
                    "type": action.get("type") or "",
                    "applied": False,
                }
                if action_type == "create-monitor":
                    values = kuma_monitor_values(action, columns)
                    if "name" not in values or "type" not in values:
                        row["error"] = "missing required monitor values"
                        result["summary"]["unsupported"] += 1
                    elif confirmed:
                        keys = list(values.keys())
                        placeholders = ",".join("?" for _ in keys)
                        conn.execute(
                            f"insert into monitor ({','.join(keys)}) values ({placeholders})",
                            [values[key] for key in keys],
                        )
                        row["applied"] = True
                        result["summary"]["created"] += 1
                    else:
                        row["would_apply"] = True
                elif action_type == "update-interval":
                    monitor_id = action.get("actual_id")
                    expected_interval = action.get("expected_interval")
                    if not isinstance(monitor_id, int) or expected_interval is None:
                        row["error"] = "missing monitor id or expected interval"
                        result["summary"]["unsupported"] += 1
                    elif confirmed:
                        conn.execute("update monitor set interval = ? where id = ?", (int(expected_interval), monitor_id))
                        row["applied"] = True
                        result["summary"]["interval_updated"] += 1
                    else:
                        row["would_apply"] = True
                elif action_type == "update-monitor":
                    monitor_id = action.get("actual_id")
                    if not isinstance(monitor_id, int):
                        row["error"] = "missing monitor id"
                        result["summary"]["unsupported"] += 1
                    else:
                        values = kuma_monitor_values(action, columns)
                        update_values = {key: value for key, value in values.items() if key in {"type", "url", "hostname", "port", "description"}}
                        if confirmed:
                            assignments = ", ".join(f"{key} = ?" for key in update_values)
                            conn.execute(
                                f"update monitor set {assignments} where id = ?",
                                [*update_values.values(), monitor_id],
                            )
                            row["applied"] = True
                            result["summary"]["review_updated"] += 1
                        else:
                            row["would_apply"] = True
                else:
                    row["ignored"] = True
                result["actions"].append(row)
    except Exception as exc:  # noqa: BLE001 - operator-facing apply result
        result["error"] = str(exc)
    finally:
        if conn is not None:
            conn.close()
    return result


def print_kuma_apply_result_markdown(result: dict[str, Any]) -> None:
    instance = result.get("instance", {})
    summary = result.get("summary", {})
    print(f"# Kuma Apply Result - {instance.get('display_name') or instance.get('name') or 'instance'}")
    print()
    print(f"- schema: `{result.get('schema')}`")
    print(f"- db: `{result.get('db_path')}`")
    print(f"- dry run: {result.get('dry_run')}")
    print(f"- confirmed: {result.get('confirmed')}")
    print(f"- backup path: `{result.get('backup_path') or ''}`")
    print(f"- selected: {summary.get('selected', 0)}")
    print(f"- created: {summary.get('created', 0)}")
    print(f"- interval updated: {summary.get('interval_updated', 0)}")
    print(f"- review updated: {summary.get('review_updated', 0)}")
    print(f"- ignored: {summary.get('ignored', 0)}")
    print(f"- unsupported: {summary.get('unsupported', 0)}")
    if result.get("error"):
        print(f"- error: `{result.get('error')}`")
    print()
    rows = [action for action in result.get("actions", []) if isinstance(action, dict)]
    if rows:
        print("| Action | Name | Type | Target | Applied |")
        print("| --- | --- | --- | --- | --- |")
        for row in rows[:120]:
            applied = row.get("applied") or row.get("would_apply") or row.get("ignored") or row.get("error") or ""
            print(f"| {row.get('action', '')} | {row.get('name', '')} | {row.get('type', '')} | `{row.get('target', '')}` | {applied} |")
        print()


def print_kuma_import_plan_markdown(plan: dict[str, Any]) -> None:
    instance = plan.get("instance", {})
    summary = plan.get("summary", {})
    print(f"# Kuma Import Plan - {instance.get('display_name') or instance.get('name') or 'instance'}")
    print()
    print(f"- schema: `{plan.get('schema')}`")
    print(f"- db: `{plan.get('db_path')}`")
    print(f"- read only: {plan.get('read_only')}")
    print(f"- backup required: {plan.get('backup_required')}")
    if plan.get("backup_command"):
        print(f"- backup command: `{plan.get('backup_command')}`")
    print(f"- actions: {summary.get('actions', 0)}")
    print(f"- creates: {summary.get('creates', 0)}")
    print(f"- updates: {summary.get('updates', 0)}")
    print(f"- optional interval updates: {summary.get('optional_interval_updates', 0)}")
    print(f"- operator-owned extras: {summary.get('operator_owned_extras', 0)}")
    print(f"- manual: {summary.get('manual', 0)}")
    print()

    def table(title: str, rows: list[dict[str, Any]], columns: list[str]) -> None:
        if not rows:
            return
        print(f"## {title}")
        print()
        print("| " + " | ".join(columns) + " |")
        print("| " + " | ".join("---" for _ in columns) + " |")
        for row in rows:
            print("| " + " | ".join(str(row.get(column, "")) for column in columns) + " |")
        print()

    actions = [item for item in plan.get("actions", []) if isinstance(item, dict)]
    table("Create", [a for a in actions if a.get("action") == "create-monitor"], ["name", "type", "target", "group", "mode"])
    table("Review Updates", [a for a in actions if a.get("action") == "update-monitor"], ["actual_id", "actual_name", "expected_name", "differences", "mode"])
    table("Optional Interval Updates", [a for a in actions if a.get("action") == "update-interval"][:80], ["actual_id", "actual_name", "expected_interval", "actual_interval", "mode"])
    table("Operator-Owned Extras", [a for a in actions if a.get("action") == "adopt-or-ignore"][:80], ["actual_id", "actual_name", "type", "target", "mode"])
    table("Manual", [a for a in actions if a.get("action") == "manual-monitor"], ["name", "type", "target", "mode"])


def print_kuma_diff_markdown(diff: dict[str, Any]) -> None:
    instance = diff.get("instance", {})
    print(f"# Kuma Monitor Diff - {instance.get('display_name') or instance.get('name') or 'instance'}")
    print()
    print(f"- schema: `{diff.get('schema')}`")
    print(f"- db: `{diff.get('db_path')}`")
    print(f"- expected auto-importable: {diff.get('expected_count', 0)}")
    print(f"- actual monitors: {diff.get('actual_count', 0)}")
    print(f"- matched: {diff.get('matched_count', 0)}")
    print(f"- changed: {diff.get('changed_count', 0)}")
    print(f"- missing: {diff.get('missing_count', 0)}")
    print(f"- extra: {diff.get('extra_count', 0)}")
    print(f"- manual candidates: {diff.get('manual_count', 0)}")
    print(f"- interval drift: {diff.get('interval_drift_count', 0)}")
    if diff.get("host_aliases"):
        aliases = ", ".join(f"{key}->{value}" for key, value in sorted(diff.get("host_aliases", {}).items()))
        print(f"- host aliases: `{aliases}`")
    print()

    def table(title: str, rows: list[dict[str, Any]], columns: list[str]) -> None:
        if not rows:
            return
        print(f"## {title}")
        print()
        print("| " + " | ".join(columns) + " |")
        print("| " + " | ".join("---" for _ in columns) + " |")
        for row in rows:
            print("| " + " | ".join(str(row.get(column, "")) for column in columns) + " |")
        print()

    table("Missing", diff.get("missing", []), ["name", "type", "target", "group"])
    table("Changed", diff.get("changed", []), ["expected_name", "actual_id", "actual_name", "differences", "target"])
    table("Extra", diff.get("extra", [])[:80], ["id", "name", "type", "target", "active"])
    table("Interval Drift", diff.get("interval_drift", [])[:80], ["expected_name", "actual_id", "actual_name", "expected_interval", "actual_interval"])
    table("Manual Candidates", diff.get("manual_candidates", []), ["name", "type", "target", "reason"])


def print_kuma_markdown(export: dict[str, Any]) -> None:
    instance = export.get("instance", {})
    print(f"# Kuma Monitor Candidates - {instance.get('display_name') or instance.get('name') or 'instance'}")
    print()
    print(f"- schema: `{export.get('schema')}`")
    print(f"- monitors: {export.get('monitor_count', 0)}")
    print(f"- auto importable: {export.get('auto_importable_count', 0)}")
    print()
    by_group: dict[str, list[dict[str, Any]]] = {}
    for monitor in export.get("monitors", []):
        if isinstance(monitor, dict):
            by_group.setdefault(str(monitor.get("group") or "Other"), []).append(monitor)
    for group, monitors in sorted(by_group.items()):
        print(f"## {group}")
        print()
        print("| Name | Type | Target | Auto | Source |")
        print("| --- | --- | --- | --- | --- |")
        for monitor in monitors:
            auto = "yes" if monitor.get("auto_importable") else "manual"
            print(f"| {monitor.get('name', '')} | {monitor.get('type', '')} | `{monitor.get('target', '')}` | {auto} | {monitor.get('source', '')} |")
        print()
