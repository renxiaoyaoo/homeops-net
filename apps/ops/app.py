import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiohttp
import yaml
from aiohttp import web

INSTANCE_DIR = Path(os.getenv("HOMENET_INSTANCE_DIR", "/homenet-instance")).resolve()
HOMENET_TOOL = Path(os.getenv("HOMENET_PLAN_TOOL", "/tools/homenet.py")).resolve()
MIHOMO_URL = os.getenv("MIHOMO_URL", "http://127.0.0.1:9090").rstrip("/")
MIHOMO_CONFIG = os.getenv("MIHOMO_CONFIG", "/mihomo-config.yaml")
MIHOMO_RUNTIME_CONFIG = os.getenv("MIHOMO_RUNTIME_CONFIG", "/root/.config/mihomo/config.yaml")
MIHOMO_CONFIG_WRITE = Path(os.getenv("MIHOMO_CONFIG_WRITE", "/mihomo-config/config.yaml")).resolve()
ROUTING_RULES_STORE = Path(os.getenv("ROUTING_RULES_STORE", "/runtime/routing/rules.json")).resolve()
ROUTING_RULE_DIR = Path(os.getenv("ROUTING_RULE_DIR", "/mihomo-rules")).resolve()
REFRESH = float(os.getenv("REFRESH", "15"))
PORT = int(os.getenv("PORT", "9999"))
OPENWRT_HOST = os.getenv("OPENWRT_HOST", "192.168.50.1")
OPENWRT_USER = os.getenv("OPENWRT_USER", "root")
ROOM_AP_IP = os.getenv("ROOM_AP_IP", "192.168.50.2")
ROOM_AP_LOCAL_IP = os.getenv("ROOM_AP_LOCAL_IP", "192.168.1.1")
OPENWRT_WAN_INTERFACE = os.getenv("OPENWRT_WAN_INTERFACE", "wan")

STATE: dict[str, Any] = {
    "ok": False,
    "updated_at": 0,
    "errors": [],
    "metadata": {},
    "instance": {"site": {}, "networks": {}, "wifi": {}, "devices": [], "services": []},
    "home_services": [],
    "ports": [],
    "devices": [],
    "foundation_checks": {"ok": False, "checks": []},
    "console": {"severity": "unknown", "headline": "Waiting for data", "layers": [], "entries": [], "unmanaged_ports": []},
}

ROUTING_POLICIES = {
    "DIRECT": {"provider": "ops-routing-direct", "label": "DIRECT"},
    "PROXY": {"provider": "ops-routing-proxy", "label": "PROXY"},
    "PROXY-JAPAN": {"provider": "ops-routing-japan", "label": "PROXY-JAPAN"},
    "AI-NODES": {"provider": "ops-routing-ai", "label": "AI-NODES"},
    "IPV6-NODES": {"provider": "ops-routing-ipv6", "label": "IPV6-NODES"},
}
ROUTING_DURATIONS = {"1h": 3600, "today": 86400, "7d": 604800, "forever": None}
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?!-)[a-z0-9*_.-]+(?<!-)$", re.I)
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
MIHOMO_SECRET_RE = re.compile(r"^\s*secret\s*:\s*(.*?)\s*$")


def add_error(message: str) -> None:
    now = time.strftime("%H:%M:%S")
    STATE["errors"] = ([f"{now} {message}"] + STATE.get("errors", []))[:8]


async def run_json_command(args: list[str], timeout: float = 12) -> dict[str, Any]:
    proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise RuntimeError("timeout")
    if proc.returncode != 0:
        detail = (err or out).decode(errors="replace").strip()[:240]
        raise RuntimeError(detail or f"exit {proc.returncode}")
    return json.loads(out.decode())


async def run_text_command(args: list[str], timeout: float = 8) -> str:
    proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise RuntimeError("timeout")
    if proc.returncode != 0:
        detail = (err or out).decode(errors="replace").strip()[:240]
        raise RuntimeError(detail or f"exit {proc.returncode}")
    return out.decode(errors="replace")


async def load_metadata() -> dict[str, Any]:
    return await run_json_command(["python", str(HOMENET_TOOL), "metadata", "--instance", str(INSTANCE_DIR)])


def instance_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "site": metadata.get("site") or {},
        "networks": metadata.get("networks") or {},
        "wifi": metadata.get("wifi") or {},
        "devices": metadata.get("devices") or [],
        "services": metadata.get("service_directory") or [],
    }


def instance_device_details() -> dict[str, dict[str, Any]]:
    try:
        doc = yaml.safe_load((INSTANCE_DIR / "devices.yaml").read_text(encoding="utf-8")) or {}
    except OSError:
        return {}
    devices = doc.get("devices") if isinstance(doc, dict) else []
    if not isinstance(devices, list):
        return {}
    return {
        str(device.get("id")): device
        for device in devices
        if isinstance(device, dict) and device.get("id")
    }


def service_ports(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for port in metadata.get("port_inventory") or []:
        if not isinstance(port, dict):
            continue
        rows.append({
            "service_key": str(port.get("service_id") or ""),
            "host": str(port.get("host") or ""),
            "port": str(port.get("port") or ""),
            "proto": str(port.get("proto") or "tcp"),
            "service": port.get("service") or port.get("service_id") or "",
            "owner": port.get("owner") or "",
            "scope": port.get("scope") or "",
            "note": port.get("note") or "",
        })
    return sorted(rows, key=lambda item: (item["host"], int(str(item["port"] or "0").split("-", 1)[0] or 0), item["proto"]))


def attach_ports(services: list[dict[str, Any]], ports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_service: dict[str, list[dict[str, Any]]] = {}
    for port in ports:
        public_port = {k: v for k, v in port.items() if k != "service_key"}
        by_service.setdefault(port.get("service_key", ""), []).append(public_port)
    for service in services:
        service["ports"] = by_service.get(service.get("key", ""), [])
    return services


def tcp_ports_from_proc(paths: tuple[str, ...] = ("/proc/net/tcp", "/proc/net/tcp6")) -> set[int]:
    ports: set[int] = set()
    for path in paths:
        try:
            lines = Path(path).read_text(encoding="utf-8").splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            parts = line.split()
            if len(parts) >= 4 and parts[3] == "0A":
                try:
                    ports.add(int(parts[1].rsplit(":", 1)[1], 16))
                except ValueError:
                    pass
    return ports


def udp_ports_from_proc(paths: tuple[str, ...] = ("/proc/net/udp", "/proc/net/udp6")) -> set[int]:
    ports: set[int] = set()
    for path in paths:
        try:
            lines = Path(path).read_text(encoding="utf-8").splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            parts = line.split()
            if len(parts) >= 2:
                try:
                    ports.add(int(parts[1].rsplit(":", 1)[1], 16))
                except ValueError:
                    pass
    return ports


async def probe_http(session: aiohttp.ClientSession, service: dict[str, Any]) -> dict[str, Any]:
    started = time.time()
    url = service.get("local_url") or ""
    try:
        async with session.get(url, allow_redirects=False) as resp:
            await resp.read()
            status = "ok" if resp.status < 400 or resp.status in {401, 403} else ("warn" if resp.status < 500 else "bad")
            detail = f"HTTP {resp.status}"
    except Exception as exc:
        status = "bad"
        detail = type(exc).__name__
    return {
        "key": service.get("id"),
        "name": service.get("name") or service.get("id"),
        "kind": service.get("category") or "other",
        "role": service.get("role") or "",
        "href": service.get("remote_url") or "",
        "local_href": service.get("local_url") or "",
        "status": status,
        "latency_ms": round((time.time() - started) * 1000),
        "detail": detail,
    }


async def probe_tcp(service: dict[str, Any], port: dict[str, Any]) -> dict[str, Any]:
    started = time.time()
    host = port.get("host") or service.get("host") or "127.0.0.1"
    raw_port = str(port.get("port") or "0").split("-", 1)[0]
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, int(raw_port)), timeout=1.3)
        writer.close()
        await writer.wait_closed()
        status = "ok"
        detail = f"tcp/{raw_port} open"
    except Exception as exc:
        status = "bad"
        detail = f"tcp/{raw_port} {type(exc).__name__}"
    return {
        "key": service.get("id"),
        "name": service.get("name") or service.get("id"),
        "kind": service.get("category") or "other",
        "role": service.get("role") or "",
        "href": service.get("remote_url") or "",
        "local_href": service.get("local_url") or "",
        "status": status,
        "latency_ms": round((time.time() - started) * 1000),
        "detail": detail,
    }


def base_service(service: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": service.get("id"),
        "name": service.get("name") or service.get("id"),
        "kind": service.get("category") or "other",
        "role": service.get("role") or "",
        "href": service.get("remote_url") or "",
        "local_href": service.get("local_url") or "",
        "status": "tracked",
        "latency_ms": 0,
        "detail": f"{service.get('runtime', 'runtime')} · {service.get('host', '')}".strip(" ·"),
    }


def severity(status: str) -> int:
    return {"bad": 4, "down": 4, "warn": 3, "unknown": 2, "tracked": 1, "ok": 0}.get(status or "unknown", 2)


def merge_services(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = row.get("key") or row.get("name")
        if key not in merged:
            merged[key] = {**merged.get(key, {}), **row}
            continue
        current_status = str(merged[key].get("status") or "")
        incoming_status = str(row.get("status") or "")
        replaces_placeholder = current_status in {"", "unknown", "tracked"} and incoming_status not in {"", "unknown", "tracked"}
        if replaces_placeholder or severity(incoming_status) > severity(current_status):
            merged[key] = {**merged[key], **row}
    return sorted(merged.values(), key=lambda item: (item.get("kind", ""), item.get("name", "")))


async def probe_services(metadata: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    services = metadata.get("service_directory") or []
    ports = service_ports(metadata)
    rows = [base_service(service) for service in services if isinstance(service, dict)]
    service_by_id = {service.get("id"): service for service in services if isinstance(service, dict)}
    timeout = aiohttp.ClientTimeout(total=2.5)
    connector = aiohttp.TCPConnector(ssl=False)
    tasks = []
    async with aiohttp.ClientSession(timeout=timeout, headers={"User-Agent": "HomeNetConsole/1.0"}, connector=connector) as session:
        for service in services:
            if not isinstance(service, dict):
                continue
            url = service.get("local_url") or ""
            if urlparse(url).scheme in {"http", "https"}:
                tasks.append(probe_http(session, service))
            else:
                first_tcp = next((p for p in ports if p.get("service_key") == service.get("id") and "tcp" in str(p.get("proto", ""))), None)
                if first_tcp:
                    tasks.append(probe_tcp(service, first_tcp))
        for result in await asyncio.gather(*tasks, return_exceptions=True):
            if isinstance(result, Exception):
                add_error(f"service probe failed: {type(result).__name__}: {result}")
            else:
                rows.append(result)

    tcp_listen = tcp_ports_from_proc()
    udp_listen = udp_ports_from_proc()
    for port in ports:
        service = service_by_id.get(port.get("service_key")) or {}
        proto = str(port.get("proto") or "")
        try:
            port_num = int(str(port.get("port") or "0").split("-", 1)[0])
        except ValueError:
            continue
        if "udp" in proto and "tcp" not in proto:
            rows.append({
                **base_service(service),
                "status": "ok" if port_num in udp_listen else "tracked",
                "detail": f"udp/{port_num} {'listening' if port_num in udp_listen else 'declared'}",
            })
        elif "tcp" in proto and port_num in tcp_listen:
            rows.append({**base_service(service), "status": "ok", "detail": f"tcp/{port_num} listening"})

    return attach_ports(merge_services(rows), ports), ports


def service_status(services: list[dict[str, Any]], key: str) -> str:
    for service in services:
        if service.get("key") == key:
            return str(service.get("status") or "unknown")
    return "unknown"


def worst(statuses: list[str]) -> str:
    return max(statuses or ["unknown"], key=severity)


def domain_status(statuses: list[str]) -> str:
    normalized = [status or "unknown" for status in statuses]
    if any(status in {"bad", "down"} for status in normalized):
        return "bad"
    if any(status == "warn" for status in normalized):
        return "warn"
    if all(status in {"ok", "tracked"} for status in normalized):
        return "ok"
    if any(status == "ok" for status in normalized) and all(status in {"ok", "tracked", "unknown"} for status in normalized):
        return "ok"
    return "unknown"


def layer(layer_id: str, title: str, status: str, detail: str, next_action: str, entry: str = "") -> dict[str, Any]:
    return {"id": layer_id, "title": title, "status": status, "detail": detail, "next_action": next_action, "entry": entry}


def check(check_id: str, title: str, status: str, detail: str, next_action: str = "", entry: str = "") -> dict[str, Any]:
    return {"id": check_id, "title": title, "status": status, "detail": detail, "next_action": next_action, "entry": entry}


def first_problem(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((item for item in sorted(items, key=lambda item: severity(str(item.get("status") or "unknown")), reverse=True) if item.get("status") in {"bad", "down", "warn", "unknown"}), None)


def expected_wifi(metadata: dict[str, Any], key: str) -> str:
    wifi = metadata.get("wifi") or {}
    item = wifi.get(key) if isinstance(wifi, dict) else {}
    return str((item or {}).get("ssid") or "")


def expected_wifi_items(metadata: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    wifi = metadata.get("wifi") or {}
    if not isinstance(wifi, dict):
        return []
    rows = []
    for key, item in wifi.items():
        if not isinstance(item, dict):
            continue
        ssid = str(item.get("ssid") or "")
        band = str(item.get("band") or "")
        purpose = str(item.get("purpose") or "")
        rows.append((str(key), ssid, band, purpose))
    return rows


def router_ssh_args(remote_command: str) -> list[str]:
    return [
        "ssh",
        "-F",
        "none",
        "-i",
        "/root/.ssh/id_ed25519",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=3",
        "-o",
        "StrictHostKeyChecking=accept-new",
        f"{OPENWRT_USER}@{OPENWRT_HOST}",
        remote_command,
    ]


def extract_block(text: str, start: str, end: str | None = None) -> str:
    if start not in text:
        return ""
    value = text.split(start, 1)[1]
    if end and end in value:
        value = value.split(end, 1)[0]
    return value.strip()


def uci_has_enabled_ssid(wireless_text: str, ssid: str) -> bool:
    if not ssid or ssid not in wireless_text:
        return False
    sections = wireless_text.split("\nwireless.")
    for section in sections:
        if f".ssid='{ssid}'" in section or f'.ssid="{ssid}"' in section or f".ssid={ssid}" in section:
            return ".disabled='1'" not in section and '.disabled="1"' not in section and ".disabled=1" not in section
    return False


def parse_radio_check(radio_text: str, radio_id: str, title: str, action: str) -> dict[str, Any]:
    try:
        parsed_radio = json.loads(radio_text)
        radio = parsed_radio.get(radio_id, parsed_radio) if isinstance(parsed_radio, dict) else {}
        radio_up = bool(radio.get("up")) and not bool(radio.get("disabled")) and not bool((radio.get("config") or {}).get("disabled")) and not bool(radio.get("retry_setup_failed"))
        interfaces = radio.get("interfaces") if isinstance(radio, dict) else []
        active_ssids = []
        for iface in interfaces if isinstance(interfaces, list) else []:
            config = iface.get("config") or {}
            ssid = config.get("ssid")
            if ssid and not config.get("disabled"):
                active_ssids.append(str(ssid))
        detail = f"{radio_id} up={radio.get('up')} disabled={radio.get('disabled') or (radio.get('config') or {}).get('disabled')} ssids={len(active_ssids)}"
        return check(radio_id, title, "ok" if radio_up else "bad", detail, action)
    except Exception:
        return check(radio_id, title, "warn", f"wifi status {radio_id} 返回无法解析。", "进入 OpenWrt 查看无线页面和系统日志。")


def parse_wan_check(wan_text: str) -> dict[str, Any]:
    try:
        wan = json.loads(wan_text)
        up = bool(wan.get("up"))
        pending = bool(wan.get("pending"))
        available = wan.get("available")
        l3_device = wan.get("l3_device") or wan.get("device") or ""
        ipv4 = wan.get("ipv4-address") or []
        ipv6 = wan.get("ipv6-address") or []
        has_addr = bool(ipv4 or ipv6)
        status = "ok" if up and has_addr else ("warn" if up or pending or available else "bad")
        detail = f"{OPENWRT_WAN_INTERFACE} up={up} addr4={len(ipv4)} addr6={len(ipv6)} dev={l3_device or 'none'}"
        return check("wan-link", "WAN / 拨号", status, detail, "WAN 异常时先看 OpenWrt 接口、PPPoE 和光猫。")
    except Exception:
        return check("wan-link", "WAN / 拨号", "warn", f"ifstatus {OPENWRT_WAN_INTERFACE} 返回无法解析。", "进入 OpenWrt 查看接口状态。")


def parse_dnsmasq_check(text: str) -> dict[str, Any]:
    normalized = text.lower()
    enabled = "enabled" in normalized
    running = "running" in normalized
    status = "ok" if enabled and running else ("warn" if enabled else "bad")
    detail = "dnsmasq enabled/running" if status == "ok" else f"dnsmasq {'enabled' if enabled else 'disabled'} / {'running' if running else 'not running'}"
    return check("router-dhcp", "DHCP / 路由 DNS", status, detail, "如果设备拿不到 IP 或显示无网络，先看 dnsmasq。")


def normalize_mac(value: str) -> str:
    return str(value or "").strip().lower()


def parse_dhcp_leases(text: str) -> dict[str, dict[str, Any]]:
    leases: dict[str, dict[str, Any]] = {}
    now = int(time.time())
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        try:
            expires_at = int(parts[0])
        except ValueError:
            expires_at = 0
        mac, ip, hostname = normalize_mac(parts[1]), parts[2], parts[3]
        leases[ip] = {
            "ip": ip,
            "mac": mac,
            "hostname": "" if hostname == "*" else hostname,
            "expires_at": expires_at,
            "active": expires_at == 0 or expires_at > now,
        }
    return leases


def parse_neighbors(text: str) -> dict[str, dict[str, Any]]:
    neighbors: dict[str, dict[str, Any]] = {}
    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        ip = parts[0]
        mac = ""
        if "lladdr" in parts:
            index = parts.index("lladdr")
            if index + 1 < len(parts):
                mac = normalize_mac(parts[index + 1])
        state = parts[-1] if parts[-1].isupper() else ""
        if mac:
            neighbors[ip] = {"ip": ip, "mac": mac, "state": state}
    return neighbors


def ip_sort_key(value: str) -> tuple[int, int, int, int]:
    try:
        return tuple(int(part) for part in value.split("."))  # type: ignore[return-value]
    except Exception:
        return (999, 999, 999, 999)


async def probe_devices(metadata: dict[str, Any]) -> dict[str, Any]:
    details = instance_device_details()
    devices = []
    for item in metadata.get("devices") or []:
        if not isinstance(item, dict):
            continue
        device_id = str(item.get("id") or "")
        devices.append({**item, **(details.get(device_id) or {})})
    for device_id, detail in details.items():
        if not any(str(item.get("id") or "") == device_id for item in devices):
            devices.append(detail)
    room_macs = {
        normalize_mac(mac)
        for device in devices
        if device.get("id") == "wrt-room"
        for mac in device.get("macs") or []
    }
    command = "echo __LEASES__; cat /tmp/dhcp.leases 2>/dev/null; echo __NEIGH__; ip neigh show 2>/dev/null"
    try:
        text = await run_text_command(router_ssh_args(command), timeout=8)
        leases = parse_dhcp_leases(extract_block(text, "__LEASES__", "__NEIGH__"))
        neighbors = parse_neighbors(extract_block(text, "__NEIGH__"))
        probe_ok = True
    except Exception as exc:
        add_error(f"device probe failed: {type(exc).__name__}: {exc}")
        leases, neighbors, probe_ok = {}, {}, False

    rows = []
    seen_ips: set[str] = set()
    for device in devices:
        ip = str(device.get("ip") or "")
        if not ip:
            continue
        seen_ips.add(ip)
        expected_macs = {normalize_mac(mac) for mac in device.get("macs") or []}
        lease = leases.get(ip) or {}
        neighbor = neighbors.get(ip) or {}
        lease_mac = normalize_mac(str(lease.get("mac") or ""))
        neighbor_mac = normalize_mac(str(neighbor.get("mac") or ""))
        current_mac = neighbor_mac or lease_mac
        lease_matches = bool(lease_mac and (not expected_macs or lease_mac in expected_macs))
        neighbor_matches = bool(neighbor_mac and (not expected_macs or neighbor_mac in expected_macs))
        via_room = bool(neighbor_mac and neighbor_mac in room_macs and lease_matches and device.get("id") != "wrt-room")
        evidence = []
        if lease:
            evidence.append("DHCP")
        if neighbor:
            evidence.append(f"neighbor {neighbor.get('state') or 'seen'}")
        presence = str(device.get("presence") or "")
        expected = bool(device.get("expected", True))
        if not probe_ok:
            status, detail = "unknown", "无法读取主路由 DHCP/neighbor 证据。"
        elif via_room:
            status = "ok"
            detail = "在线，经 WRT Room 中继/proxy ARP"
        elif neighbor_matches or lease_matches:
            status = "ok"
            detail = "在线"
        elif current_mac and expected_macs and current_mac not in expected_macs:
            status = "warn"
            detail = "IP 当前 MAC 与声明不一致"
        elif lease or neighbor:
            status = "ok"
            detail = "在线，未声明 MAC"
        elif not expected:
            status = "tracked"
            detail = "保留设备，当前未在线"
        elif presence in {"optional", "intermittent"}:
            status = "sleeping"
            detail = "可离线/间歇在线"
        else:
            status = "offline"
            detail = "未在线"
        rows.append({
            "id": device.get("id"),
            "name": device.get("name") or device.get("id"),
            "role": device.get("role") or "",
            "network": device.get("network") or "",
            "ip": ip,
            "expected": expected,
            "presence": presence,
            "expected_macs": sorted(expected_macs),
            "current_mac": current_mac,
            "lease_mac": lease_mac,
            "neighbor_mac": neighbor_mac,
            "hostname": lease.get("hostname") or (device.get("hostnames") or [""])[0],
            "neighbor_state": neighbor.get("state") or "",
            "status": status,
            "detail": detail,
            "evidence": evidence,
            "via_room_relay": via_room,
        })

    for ip, lease in leases.items():
        if ip in seen_ips:
            continue
        neighbor = neighbors.get(ip) or {}
        rows.append({
            "id": f"unknown-{ip}",
            "name": lease.get("hostname") or "未知设备",
            "role": "DHCP lease",
            "network": "",
            "ip": ip,
            "expected": False,
            "presence": "",
            "expected_macs": [],
            "current_mac": neighbor.get("mac") or lease.get("mac") or "",
            "lease_mac": lease.get("mac") or "",
            "neighbor_mac": neighbor.get("mac") or "",
            "hostname": lease.get("hostname") or "",
            "neighbor_state": neighbor.get("state") or "",
            "status": "warn",
            "detail": "DHCP 中存在但 instance 未声明",
            "evidence": ["DHCP"] + ([f"neighbor {neighbor.get('state')}"] if neighbor else []),
            "via_room_relay": False,
        })

    return {
        "ok": probe_ok,
        "updated_at": time.time(),
        "summary": {
            "total": len(rows),
            "online": sum(1 for row in rows if row["status"] == "ok"),
            "attention": sum(1 for row in rows if row["status"] in {"warn", "offline"}),
            "standby": sum(1 for row in rows if row["status"] in {"sleeping", "tracked"}),
        },
        "items": sorted(rows, key=lambda row: ip_sort_key(str(row.get("ip") or ""))),
    }


async def probe_foundation_checks(metadata: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    command = (
        "echo __WAN__; "
        f"ifstatus {OPENWRT_WAN_INTERFACE} 2>/dev/null || ubus call network.interface.{OPENWRT_WAN_INTERFACE} status 2>/dev/null || true; "
        "echo __RADIO0__; "
        "wifi status radio0 2>/dev/null; "
        "echo __RADIO1__; "
        "wifi status radio1 2>/dev/null; "
        "echo __WIRELESS__; "
        "uci show wireless 2>/dev/null | grep -E \"\\.ssid=|\\.network=|\\.disabled=|\\.mode=|\\.device=\"; "
        "echo __DNSMASQ__; "
        "(/etc/init.d/dnsmasq enabled >/dev/null 2>&1 && echo enabled || echo disabled); "
        "/etc/init.d/dnsmasq status 2>/dev/null || true; "
        "echo __ROOM__; "
        f"ping -c 1 -W 1 {ROOM_AP_IP} >/dev/null 2>&1 && echo up || echo down"
    )
    try:
        text = await run_text_command(router_ssh_args(command), timeout=8)
    except Exception as exc:
        detail = f"主路由 SSH 只读探测失败：{type(exc).__name__}"
        return {
            "ok": False,
            "updated_at": time.time(),
            "checks": [
                check("router-probe", "主路由基础探测", "warn", detail, "先确认 OpenWrt SSH 是否可达。"),
                check("room-ap", "卧室 WRT", "unknown", f"未能通过主路由 ping {ROOM_AP_IP}。", "主路由探测恢复后再看卧室 WRT。", f"http://{ROOM_AP_IP}/"),
            ],
            "room_side_entry": f"http://{ROOM_AP_LOCAL_IP}/",
        }

    wan_text = extract_block(text, "__WAN__", "__RADIO0__")
    radio0_text = extract_block(text, "__RADIO0__", "__RADIO1__")
    radio_text = extract_block(text, "__RADIO1__", "__WIRELESS__")
    wireless_text = extract_block(text, "__WIRELESS__", "__DNSMASQ__")
    dnsmasq_text = extract_block(text, "__DNSMASQ__", "__ROOM__")
    room_text = extract_block(text, "__ROOM__")

    checks.append(parse_wan_check(wan_text))
    checks.append(parse_dnsmasq_check(dnsmasq_text))
    checks.append(parse_radio_check(radio0_text, "radio0", "主路由 2.4G radio", "IoT、Ops 或部分设备异常时，先看 2.4G radio。"))
    checks.append(parse_radio_check(radio_text, "radio1", "主路由 5G radio", "5G 异常时，先重启无线或查看 OpenWrt wireless 日志。"))

    for wifi_key, ssid, band, purpose in expected_wifi_items(metadata):
        title = {
            "main": "主 Wi-Fi",
            "relay_5g": "卧室回程",
            "ops": "检修 Wi-Fi",
            "iot": "IoT Wi-Fi",
            "guest": "访客 Wi-Fi",
        }.get(wifi_key, f"Wi-Fi {wifi_key}")
        action = {
            "main": "主 SSID 没广播会导致日常设备断网。",
            "relay_5g": "回程 SSID 没广播会导致卧室 WRT 掉线。",
            "ops": "检修 Wi-Fi 没广播会影响故障时用设备进 Pi。",
            "iot": "IoT Wi-Fi 没广播会影响智能家居和摄像头。",
            "guest": "访客 Wi-Fi 没广播只影响访客网络。",
        }.get(wifi_key, purpose or "检查 OpenWrt wireless。")
        check_id = f"wifi-{wifi_key}"
        if not ssid:
            checks.append(check(check_id, title, "unknown", "实例未声明 SSID。", "检查 instance wifi 定义。"))
        elif uci_has_enabled_ssid(wireless_text, ssid):
            checks.append(check(check_id, title, "ok", f"{ssid} 已启用 · {band or 'band unknown'}"))
        else:
            checks.append(check(check_id, title, "bad", f"{ssid} 未在 OpenWrt wireless 中启用或未找到。", action))

    room_up = room_text.splitlines()[-1].strip() == "up" if room_text.splitlines() else False
    checks.append(check("room-ap", "卧室 WRT", "ok" if room_up else "bad", f"{ROOM_AP_IP} {'可达' if room_up else '不可达'}。", "卧室 WRT 不可达时，先看回程 SSID 和设备供电。", f"http://{ROOM_AP_IP}/"))

    return {
        "ok": not any(item.get("status") in {"bad", "down", "warn"} for item in checks),
        "updated_at": time.time(),
        "checks": checks,
        "room_side_entry": f"http://{ROOM_AP_LOCAL_IP}/",
    }


def build_console(metadata: dict[str, Any], services: list[dict[str, Any]], ports: list[dict[str, Any]], foundation_checks: dict[str, Any] | None = None) -> dict[str, Any]:
    gateway = domain_status([service_status(services, "openwrt-luci"), service_status(services, "openwrt-ssh")])
    foundation_checks = foundation_checks or {"checks": []}
    foundation_items = list(foundation_checks.get("checks") or [])
    foundation_by_id = {item.get("id"): item for item in foundation_items}
    wifi_keys = ["radio0", "radio1", "wifi-main", "wifi-relay_5g", "wifi-iot", "wifi-guest", "wifi-ops"]
    wifi_status = domain_status([str((foundation_by_id.get(key) or {}).get("status") or "unknown") for key in wifi_keys])
    wifi_problem = first_problem([foundation_by_id.get(key) for key in wifi_keys if foundation_by_id.get(key)] or [])
    room_probe = str((foundation_by_id.get("room-ap") or {}).get("status") or "unknown")
    room = domain_status([service_status(services, "wrt-room-luci"), service_status(services, "wrt-room-ssh"), room_probe])
    dns_proxy = domain_status([service_status(services, "adguard"), service_status(services, "mihomo")])
    runtime = domain_status([service_status(services, key) for key in ["homenet-ops", "adguard", "mihomo", "home-assistant", "uptime-kuma", "cloudflared", "wireguard"]])
    remote = domain_status([service_status(services, key) for key in ["cloudflared", "wireguard", "caddy", "ddns-go"]])
    rescue = domain_status([service_status(services, "homenet-ops"), service_status(services, "pi-ssh"), str((foundation_by_id.get("wifi-ops") or {}).get("status") or "unknown")])
    wan_probe = str((foundation_by_id.get("wan-link") or {}).get("status") or "unknown")
    gateway = domain_status([gateway, wan_probe, str((foundation_by_id.get("router-dhcp") or {}).get("status") or "unknown")])
    room_detail = str((foundation_by_id.get("room-ap") or {}).get("detail") or "卧室覆盖由 WRT Room 承担。")

    layers = [
        layer("rescue-path", "检修通道", "ok" if rescue == "ok" else "warn", "Ops Wi-Fi、Console、Pi SSH 组成检修入口。", "主网络复杂路径坏了，连检修 Wi-Fi 后从这里进 Pi。"),
        layer("gateway-wan", "主路由 / WAN", gateway, "OpenWrt LuCI/SSH 是基础入口。", "如果这里异常，先查 OpenWrt WAN、DHCP、接口和防火墙。"),
        layer("main-wifi-5g", "Wi-Fi / Radio", wifi_status, str((wifi_problem or {}).get("detail") or "2.4G、5G 和声明的 SSID 已检查。"), "Wi-Fi 异常时先看 OpenWrt wireless/radio，不改 DNS/Proxy。"),
        layer("room-ap", "卧室 WRT", room, room_detail, "卧室慢时先查 WRT Room 回程和管理入口，不做全网重构。", f"http://{ROOM_AP_IP}/"),
        layer("dns-proxy", "DNS / Proxy", dns_proxy, "AdGuard 负责 DNS，Mihomo 负责代理和分流。", "国内慢看 DIRECT/DNS，国外慢看 Mihomo 节点组和规则。"),
        layer("server-runtime", "Pi 服务", runtime, "Pi 承载 DNS、Proxy、HA、Kuma、WireGuard、Console 等服务。", "多个服务一起异常时先查 Docker/systemd/端口。"),
        layer("remote-access", "外部回家", remote, "外部入口由 Cloudflare、WireGuard、Caddy、DDNS 共同承担。", "本地入口正常后，再查 Cloudflare/WireGuard/Caddy。"),
    ]

    active = next((item for item in layers if item["status"] in {"bad", "down", "warn"}), None)
    overall = "bad" if any(item["status"] in {"bad", "down"} for item in layers) else ("warn" if active else "ok")
    declared_tcp = {
        int(str(port.get("port") or "0").split("-", 1)[0])
        for port in ports
        if "tcp" in str(port.get("proto", "")) and str(port.get("port") or "0").split("-", 1)[0].isdigit()
    }
    unmanaged = sorted(tcp_ports_from_proc() - declared_tcp)
    entries = []
    for key in ["homenet-ops", "openwrt-luci", "wrt-room-luci", "mihomo", "adguard", "home-assistant", "uptime-kuma", "wireguard"]:
        service = next((item for item in services if item.get("key") == key), None)
        if service:
            entries.append({
                "id": key,
                "label": service.get("name"),
                "name": service.get("name"),
                "status": service.get("status"),
                "local_href": service.get("local_href"),
                "href": service.get("href"),
                "role": service.get("role"),
            })

    return {
        "ok": overall == "ok",
        "severity": overall,
        "headline": "关键链路正常" if overall == "ok" else f"先看：{active['title'] if active else '当前状态'}",
        "active_problem": active,
        "layers": layers,
        "entries": entries,
        "foundation_checks": foundation_items,
        "room_side_entry": foundation_checks.get("room_side_entry") or f"http://{ROOM_AP_LOCAL_IP}/",
        "unmanaged_ports": unmanaged[:16],
        "unmanaged_port_count": len(unmanaged),
        "current_error_count": len(STATE.get("errors") or []),
        "updated_at": time.time(),
        "model": "public HomeNet core + private instance",
        "source_of_truth": "instance metadata + live service probes",
    }


async def refresh_state() -> None:
    try:
        metadata = await load_metadata()
        services, ports = await probe_services(metadata)
        foundation_checks = await probe_foundation_checks(metadata)
        devices = await probe_devices(metadata)
        STATE.update({
            "ok": True,
            "metadata": {"schema": metadata.get("schema"), "profile": metadata.get("profile")},
            "instance": instance_from_metadata(metadata),
            "home_services": services,
            "ports": [{k: v for k, v in port.items() if k != "service_key"} for port in ports],
            "devices": devices,
            "foundation_checks": foundation_checks,
            "console": build_console(metadata, services, ports, foundation_checks),
            "updated_at": time.time(),
        })
    except Exception as exc:
        add_error(f"refresh failed: {type(exc).__name__}: {exc}")
        STATE["ok"] = False
        STATE["updated_at"] = time.time()


def normalize_target(raw: str) -> dict[str, str]:
    value = (raw or "").strip()
    if not value:
        raise ValueError("empty target")
    parsed = urlparse(value if "://" in value else f"//{value}")
    host = (parsed.hostname or value.split("/", 1)[0]).lower().strip().rstrip(".")
    if IPV4_RE.fullmatch(host):
        return {"kind": "ip", "value": host, "rule": f"IP-CIDR,{host}/32,no-resolve"}
    if ":" in host:
        return {"kind": "ip6", "value": host, "rule": f"IP-CIDR6,{host}/128,no-resolve"}
    host = host.replace("www.", "", 1)
    if host.startswith("*."):
        host = host[2:]
    if not DOMAIN_RE.fullmatch(host) or "." not in host:
        raise ValueError("target must be a domain name or IP address")
    return {"kind": "domain", "value": host, "rule": f"DOMAIN-SUFFIX,{host}"}


def read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else default
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def routing_store() -> dict[str, Any]:
    data = read_json(ROUTING_RULES_STORE, {})
    return {
        "entries": [item for item in data.get("entries", []) if isinstance(item, dict)],
        "permanent_candidates": [item for item in data.get("permanent_candidates", []) if isinstance(item, dict)],
    }


def save_routing_store(data: dict[str, Any]) -> None:
    write_json(ROUTING_RULES_STORE, {
        "schema": "homenet.routing-rules.v1",
        "updated_at": time.time(),
        "entries": sorted(data.get("entries") or [], key=lambda item: (item.get("policy", ""), item.get("value", ""))),
        "permanent_candidates": sorted(data.get("permanent_candidates") or [], key=lambda item: (item.get("policy", ""), item.get("value", ""))),
    })


def active_entries(data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    now = time.time()
    data = data or routing_store()
    active = [item for item in data.get("entries", []) if not item.get("expires_at") or float(item["expires_at"]) > now]
    if len(active) != len(data.get("entries", [])):
        save_routing_store({**data, "entries": active})
    return active


def candidate_entries(data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return (data or routing_store()).get("permanent_candidates", [])


def rules_yaml(rules: list[str]) -> str:
    return "payload:\n" + "".join(f"  - {json.dumps(rule, ensure_ascii=False)}\n" for rule in rules)


def write_runtime_rules(entries: list[dict[str, Any]]) -> None:
    ROUTING_RULE_DIR.mkdir(parents=True, exist_ok=True)
    grouped = {meta["provider"]: [] for meta in ROUTING_POLICIES.values()}
    for item in entries:
        meta = ROUTING_POLICIES.get(str(item.get("policy")))
        if meta and item.get("rule"):
            grouped[meta["provider"]].append(str(item["rule"]))
    for provider, rules in grouped.items():
        (ROUTING_RULE_DIR / f"{provider}.yaml").write_text(rules_yaml(rules), encoding="utf-8")


def load_mihomo_secret() -> str:
    try:
        for line in Path(MIHOMO_CONFIG).read_text(encoding="utf-8").splitlines():
            match = MIHOMO_SECRET_RE.match(line)
            if match:
                value = match.group(1).strip()
                return value[1:-1] if len(value) >= 2 and value[0] in "'\"" and value[-1] == value[0] else value
    except OSError:
        pass
    return os.getenv("MIHOMO_SECRET", "")


def ensure_overlay() -> None:
    if not MIHOMO_CONFIG_WRITE.exists():
        return
    config = yaml.safe_load(MIHOMO_CONFIG_WRITE.read_text(encoding="utf-8")) or {}
    providers = config.setdefault("rule-providers", {})
    rules = config.setdefault("rules", [])
    overlay = []
    for policy in ["DIRECT", "PROXY-JAPAN", "AI-NODES", "IPV6-NODES", "PROXY"]:
        provider = ROUTING_POLICIES[policy]["provider"]
        providers[provider] = {"type": "file", "behavior": "classical", "format": "yaml", "path": f"./rules/{provider}.yaml"}
        overlay.append(f"RULE-SET,{provider},{policy}")
    config["rules"] = overlay + [rule for rule in rules if rule not in overlay]
    MIHOMO_CONFIG_WRITE.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")


async def reload_mihomo() -> tuple[bool, str]:
    secret = load_mihomo_secret()
    headers = {"Authorization": f"Bearer {secret}"} if secret else {}
    timeout = aiohttp.ClientTimeout(total=5)
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        async with session.put(f"{MIHOMO_URL}/configs", json={"path": MIHOMO_RUNTIME_CONFIG}) as resp:
            detail = await resp.text()
            return resp.status < 300, detail[:240]


async def apply_routing() -> tuple[bool, str]:
    write_runtime_rules(active_entries())
    try:
        ensure_overlay()
        return await reload_mihomo()
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


async def api_state(request: web.Request) -> web.Response:
    return web.json_response(STATE)


async def api_health(request: web.Request) -> web.Response:
    console = STATE.get("console") or {}
    checks = [
        {
            "status": layer.get("status"),
            "title": layer.get("title"),
            "detail": layer.get("detail"),
        }
        for layer in console.get("layers", [])
    ]
    return web.json_response({
        "ok": bool(console.get("ok")),
        "updated_at": console.get("updated_at") or STATE.get("updated_at"),
        "checks": checks,
        "errors": STATE.get("errors") or [],
    })


async def api_routing_rules(request: web.Request) -> web.Response:
    data = routing_store()
    return web.json_response({
        "ok": True,
        "policies": [{"id": key, "label": meta["label"]} for key, meta in ROUTING_POLICIES.items()],
        "durations": list(ROUTING_DURATIONS.keys()),
        "entries": active_entries(data),
        "permanent_candidates": candidate_entries(data),
        "updated_at": time.time(),
    })


async def api_routing_add(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
        target = normalize_target(str(payload.get("target") or ""))
        policy = str(payload.get("policy") or "PROXY").upper()
        if policy not in ROUTING_POLICIES:
            raise ValueError(f"unsupported policy {policy}")
        permanent = bool(payload.get("permanent"))
        duration = str(payload.get("duration") or "1h")
        if not permanent and duration not in ROUTING_DURATIONS:
            raise ValueError(f"unsupported duration {duration}")
    except (json.JSONDecodeError, ValueError) as exc:
        return web.json_response({"ok": False, "error": str(exc)}, status=400)

    now = time.time()
    item = {
        "id": f"temporary:{policy}:{target['value']}",
        "scope": "temporary",
        "policy": policy,
        "kind": target["kind"],
        "value": target["value"],
        "rule": target["rule"],
        "duration": duration,
        "created_at": now,
        "expires_at": None if permanent else (None if ROUTING_DURATIONS[duration] is None else now + int(ROUTING_DURATIONS[duration] or 0)),
    }
    data = routing_store()
    if permanent:
        candidate = {**item, "id": f"permanent-pending:{policy}:{target['value']}", "status": "pending"}
        candidates = [row for row in candidate_entries(data) if row.get("id") != candidate["id"]]
        save_routing_store({**data, "permanent_candidates": [*candidates, candidate]})
        return web.json_response({"ok": True, "entries": active_entries(), "permanent_candidates": candidate_entries(), "detail": "permanent candidate created"})

    entries = [row for row in active_entries(data) if row.get("id") != item["id"]]
    save_routing_store({**data, "entries": [*entries, item]})
    ok, detail = await apply_routing()
    return web.json_response({"ok": ok, "detail": detail, "entries": active_entries(), "permanent_candidates": candidate_entries()}, status=200 if ok else 502)


async def api_routing_delete(request: web.Request) -> web.Response:
    rule_id = request.match_info["rule_id"]
    data = routing_store()
    save_routing_store({**data, "entries": [row for row in active_entries(data) if row.get("id") != rule_id]})
    ok, detail = await apply_routing()
    return web.json_response({"ok": ok, "detail": detail, "entries": active_entries(), "permanent_candidates": candidate_entries()}, status=200 if ok else 502)


async def api_routing_promote(request: web.Request) -> web.Response:
    rule_id = request.match_info["rule_id"]
    data = routing_store()
    source = next((row for row in active_entries(data) if row.get("id") == rule_id), None)
    if not source:
        return web.json_response({"ok": False, "error": "rule not found"}, status=404)
    candidate = {**source, "id": f"permanent-pending:{source.get('policy')}:{source.get('value')}", "status": "pending"}
    candidates = [row for row in candidate_entries(data) if row.get("id") != candidate["id"]]
    save_routing_store({**data, "permanent_candidates": [*candidates, candidate]})
    return web.json_response({"ok": True, "entries": active_entries(), "permanent_candidates": candidate_entries()})


async def api_permanent_delete(request: web.Request) -> web.Response:
    candidate_id = request.match_info["candidate_id"]
    data = routing_store()
    save_routing_store({**data, "permanent_candidates": [row for row in candidate_entries(data) if row.get("id") != candidate_id]})
    return web.json_response({"ok": True, "entries": active_entries(), "permanent_candidates": candidate_entries()})


async def events(request: web.Request) -> web.StreamResponse:
    response = web.StreamResponse(headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache", "Connection": "keep-alive"})
    await response.prepare(request)
    try:
        while True:
            await response.write(f"data: {json.dumps(STATE, ensure_ascii=False)}\n\n".encode())
            await asyncio.sleep(REFRESH)
    except (asyncio.CancelledError, ConnectionResetError):
        pass
    return response


async def index(request: web.Request) -> web.Response:
    return web.FileResponse(Path(__file__).with_name("static") / "index.html")


async def sampler(app: web.Application) -> None:
    while True:
        await refresh_state()
        await asyncio.sleep(REFRESH)


async def on_startup(app: web.Application) -> None:
    await refresh_state()
    app["sampler"] = asyncio.create_task(sampler(app))


async def on_cleanup(app: web.Application) -> None:
    app["sampler"].cancel()
    await asyncio.gather(app["sampler"], return_exceptions=True)


app = web.Application()
app.on_startup.append(on_startup)
app.on_cleanup.append(on_cleanup)
app.router.add_get("/api/state", api_state)
app.router.add_get("/api/health", api_health)
app.router.add_get("/events", events)
app.router.add_get("/api/routing-rules", api_routing_rules)
app.router.add_post("/api/routing-rules", api_routing_add)
app.router.add_delete("/api/routing-rules/{rule_id:.+}", api_routing_delete)
app.router.add_post("/api/routing-rules/{rule_id:.+}/promote", api_routing_promote)
app.router.add_delete("/api/routing-permanent/{candidate_id:.+}", api_permanent_delete)
app.router.add_static("/assets/", Path(__file__).with_name("static") / "assets")
app.router.add_get("/{tail:.*}", index)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
