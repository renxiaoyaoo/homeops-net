from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def service_module_id(service: dict[str, Any]) -> str:
    service_id = str(service.get("id") or "").lower()
    category = str(service.get("category") or "").lower()
    owner = str(service.get("owner") or "").lower()
    runtime = str(service.get("runtime") or "").lower()
    if service_id.startswith("wrt-room") or service_id.startswith("room-ap"):
        return "room-ap"
    if category == "remote-entry":
        return "remote-access"
    if category == "home-core":
        return "smart-home"
    if category in {"control-core", "system-task"}:
        if "adguard" in service_id or "dns" in service_id:
            return "dns-layer"
        if "mihomo" in service_id or "proxy" in service_id:
            return "proxy-mihomo"
        return "observability-homenet"
    if category == "gateway":
        if "dns" in service_id:
            return "dns-layer"
        if "mihomo" in service_id or "proxy" in service_id:
            return "proxy-mihomo"
        return "gateway-openwrt"
    if category == "network-core":
        if "adguard" in owner or "adguard" in service_id or "dns" in service_id:
            return "dns-layer"
        if "mihomo" in owner or "mihomo" in service_id or "proxy" in service_id:
            return "proxy-mihomo"
        if "wireguard" in service_id or "cloudflared" in service_id or "caddy" in service_id or "ddns" in service_id:
            return "remote-access"
        return "gateway-openwrt"
    if category in {"storage", "daily-app"}:
        return "server-runtime"
    if runtime == "server":
        return "server-runtime"
    if runtime == "openwrt":
        return "gateway-openwrt"
    return "observability-homenet"


def service_module_state(service: dict[str, Any], enabled_by_module: dict[str, bool]) -> dict[str, Any]:
    module_id = service_module_id(service)
    enabled = enabled_by_module.get(module_id, True)
    return {
        "module_id": module_id,
        "module_enabled": enabled,
        "module_status": "active" if enabled else "disabled-by-module",
    }


def build_service_directory(services: list[dict[str, Any]], enabled_by_module: dict[str, bool] | None = None) -> list[dict[str, Any]]:
    module_state = enabled_by_module or {}
    rows: list[dict[str, Any]] = []
    for service in services:
        if not isinstance(service, dict):
            continue
        service_id = str(service.get("id") or "")
        if not service_id:
            continue
        state = service_module_state(service, module_state)
        rows.append({
            "id": service_id,
            "name": service.get("name") or service_id,
            "category": service.get("category") or "other",
            "module_id": state.get("module_id") or "",
            "module_enabled": state.get("module_enabled"),
            "module_status": state.get("module_status") or "",
            "role": service.get("role") or "",
            "runtime": service.get("runtime") or "",
            "host": service.get("host") or "",
            "owner": service.get("owner") or "",
            "local_url": service.get("local_url") or "",
            "remote_url": service.get("remote_url") or "",
            "has_web_entry": bool(service.get("local_url") or service.get("remote_url")),
            "has_ports": bool(service.get("ports")),
            "has_checks": bool(service.get("checks")),
        })
    return sorted(rows, key=lambda item: (str(item.get("category", "")), str(item.get("name", ""))))


def build_port_inventory(services: list[dict[str, Any]], enabled_by_module: dict[str, bool] | None = None) -> list[dict[str, Any]]:
    module_state = enabled_by_module or {}
    rows: list[dict[str, Any]] = []
    for service in services:
        if not isinstance(service, dict):
            continue
        service_id = str(service.get("id") or "")
        state = service_module_state(service, module_state)
        for port in as_list(service.get("ports")):
            if not isinstance(port, dict):
                continue
            rows.append({
                "service_id": service_id,
                "service": service.get("name") or service_id,
                "module_id": state.get("module_id") or "",
                "module_enabled": state.get("module_enabled"),
                "module_status": state.get("module_status") or "",
                "host": str(port.get("host") or service.get("host") or ""),
                "port": str(port.get("port") or ""),
                "proto": str(port.get("proto") or "tcp"),
                "scope": port.get("scope") or "",
                "owner": service.get("owner") or service.get("runtime") or "",
                "note": port.get("note") or service.get("role") or "",
            })
    return sorted(
        rows,
        key=lambda item: (
            str(item.get("host", "")),
            int(str(item.get("port", "0")).split("-")[0]) if str(item.get("port", "0")).split("-")[0].isdigit() else 0,
            str(item.get("proto", "")),
            str(item.get("service", "")),
        ),
    )


def build_kuma_inventory(services: list[dict[str, Any]], enabled_by_module: dict[str, bool] | None = None) -> list[dict[str, Any]]:
    module_state = enabled_by_module or {}
    rows: list[dict[str, Any]] = []
    for service in services:
        if not isinstance(service, dict):
            continue
        service_id = str(service.get("id") or "")
        if not service_id:
            continue
        state = service_module_state(service, module_state)
        if state.get("module_enabled") is False:
            continue
        remote_url = str(service.get("remote_url") or "")
        local_url = str(service.get("local_url") or "")
        remote_scheme = urlparse(remote_url).scheme.lower() if remote_url else ""
        local_parsed = urlparse(local_url) if local_url else None
        local_scheme = local_parsed.scheme.lower() if local_parsed else ""
        local_monitor_port = ""
        if local_parsed and local_scheme in {"http", "https"}:
            local_monitor_port = str(local_parsed.port or (443 if local_scheme == "https" else 80))
        if remote_url and remote_scheme in {"http", "https"}:
            rows.append({
                "service_id": service_id,
                "name": service.get("name") or service_id,
                "monitor_type": "http",
                "target": remote_url,
                "scope": "remote",
                "module_id": state.get("module_id") or "",
                "source": "services.yaml remote_url",
            })
        elif remote_url and remote_scheme:
            rows.append({
                "service_id": service_id,
                "name": service.get("name") or service_id,
                "monitor_type": remote_scheme,
                "target": remote_url,
                "scope": "remote",
                "module_id": state.get("module_id") or "",
                "source": "services.yaml remote_url",
            })
        elif local_url and local_scheme in {"http", "https"}:
            rows.append({
                "service_id": service_id,
                "name": service.get("name") or service_id,
                "monitor_type": "http",
                "target": local_url,
                "scope": "lan",
                "module_id": state.get("module_id") or "",
                "source": "services.yaml local_url",
            })

        for port in as_list(service.get("ports")):
            if not isinstance(port, dict):
                continue
            proto = str(port.get("proto") or "tcp").lower()
            if "tcp" not in proto:
                continue
            host = str(port.get("host") or service.get("host") or "")
            p_port = str(port.get("port") or "")
            if not host or not p_port:
                continue
            if local_scheme in {"http", "https"} and p_port == local_monitor_port:
                continue
            rows.append({
                "service_id": service_id,
                "name": f"{service.get('name') or service_id} tcp/{p_port}",
                "monitor_type": "tcp",
                "target": f"{host}:{p_port}",
                "scope": port.get("scope") or "",
                "module_id": state.get("module_id") or "",
                "source": "services.yaml ports",
            })
    return sorted(rows, key=lambda item: (str(item.get("service_id", "")), str(item.get("monitor_type", "")), str(item.get("target", ""))))
