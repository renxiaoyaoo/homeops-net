import asyncio
import json
import os
import re
import subprocess
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import urlparse, urlunparse

import aiohttp
import yaml
from aiohttp import web

OPENWRT_HOST = os.getenv("OPENWRT_HOST", "192.168.50.1")
OPENWRT_USER = os.getenv("OPENWRT_USER", "root")
HOMENET_SERVER_IP = os.getenv("HOMENET_SERVER_IP", "192.168.50.5")
ROOM_AP_IP = os.getenv("ROOM_AP_IP", "192.168.50.2")
ROOM_AP_LOCAL_IP = os.getenv("ROOM_AP_LOCAL_IP", "192.168.1.1")
WAN_IF = os.getenv("WAN_IF", "pppoe-wan")
MIHOMO_URL = os.getenv("MIHOMO_URL", "http://127.0.0.1:9090").rstrip("/")
MIHOMO_CONTROLLER_CREDENTIAL = os.getenv("MIHOMO_SECRET", "")
MIHOMO_CONFIG = os.getenv("MIHOMO_CONFIG", "/mihomo-config.yaml")
MIHOMO_RUNTIME_CONFIG = os.getenv("MIHOMO_RUNTIME_CONFIG", "/root/.config/mihomo/config.yaml")
MIHOMO_CONFIG_WRITE = Path(os.getenv("MIHOMO_CONFIG_WRITE", "/mihomo-config/config.yaml")).resolve()
ROUTING_RULES_STORE = Path(os.getenv("ROUTING_RULES_STORE", "/runtime/routing/rules.json")).resolve()
ROUTING_RULE_DIR = Path(os.getenv("ROUTING_RULE_DIR", "/mihomo-rules")).resolve()
ADGUARD_DOMESTIC_FILE = os.getenv("ADGUARD_DOMESTIC_FILE", "/adguard-conf/upstream-domestic.conf")
PRESENCE_URL = os.getenv("PRESENCE_URL", "http://127.0.0.1:9977/state").strip()
WIREGUARD_STATUS_FILE = os.getenv("WIREGUARD_STATUS_FILE", "/maintenance-state/wireguard/clients.json").strip()
INSTANCE_DIR = Path(os.getenv("HOMENET_INSTANCE_DIR", "/homenet-instance")).resolve()
HOMENET_PLAN_TOOL = Path(os.getenv("HOMENET_PLAN_TOOL", "/tools/homenet.py")).resolve()
REFRESH = float(os.getenv("REFRESH", "15"))
DHCP_INTERVAL = float(os.getenv("DHCP_INTERVAL", "60"))
SERVICE_PROBE_INTERVAL = float(os.getenv("SERVICE_PROBE_INTERVAL", "60"))
HEAVY_PROBE_INTERVAL = float(os.getenv("HEAVY_PROBE_INTERVAL", "120"))
HEALTH_INTERVAL = float(os.getenv("HEALTH_INTERVAL", "90"))
ERROR_TTL = float(os.getenv("ERROR_TTL", "900"))
METADATA_TIMEOUT = float(os.getenv("METADATA_TIMEOUT", "12"))
SSH_OPTS = [
    "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=3",
    "-o", "StrictHostKeyChecking=accept-new",
    "-o", "ServerAliveInterval=10",
    "-o", "ServerAliveCountMax=2",
]

STATE = {
    "ok": False,
    "updated_at": 0,
    "errors": [],
    "error_events": [],
    "wan": {"down_mbps": 0, "up_mbps": 0, "rx_bytes": 0, "tx_bytes": 0},
    "devices": [],
    "domains": [],
    "dns_queries": [],
    "dns_top_devices": [],
    "dns_top_hosts": [],
    "connections": [],
    "route_summary": [],
    "insights": [],
    "health": {"updated_at": 0, "checks": []},
    "history": [],
    "mihomo": {"up_mbps": 0, "down_mbps": 0},
    "home_services": [],
    "ingress": [],
    "ports": [],
    "presence": {"ok": False, "merged_clients": [], "fresh_aps": [], "aps": {}, "last_ha_push": {}, "updated_at": 0},
    "remote_access": {"ok": False, "clients": [], "updated_at": 0},
    "ops_network": {"ok": False, "checks": [], "clients": [], "updated_at": 0},
    "wifi_diagnostics": {"ok": False, "checks": [], "updated_at": 0},
    "incident": {"ok": False, "domains": [], "decision_flow": [], "recovery_matrix": [], "runbook": [], "updated_at": 0},
    "metadata": {"ok": False, "schema": "", "updated_at": 0},
    "instance": {"ok": False, "site": {}, "networks": {}, "wifi": {}, "devices": [], "services": [], "updated_at": 0},
    "plan": {"ok": False, "schema": "", "modules": [], "updated_at": 0},
    "blueprint": {"ok": False, "schema": "", "active_capabilities": [], "updated_at": 0},
}

HTTP_PROBE_OVERRIDES = {
    "adguard": {"path": "/", "probe_host": "127.0.0.1", "probe_port": "3000"},
    "asset-guardian": {"path": "/api/health", "probe_host": "127.0.0.1"},
    "balcony-grow": {"probe_host": "127.0.0.1"},
    "ddns-go": {"probe_host": "127.0.0.1"},
    "filebrowser": {"probe_host": "127.0.0.1"},
    "home-assistant": {"probe_host": "127.0.0.1"},
    "homenet-ops": {"path": "/api/state", "probe_host": "127.0.0.1"},
    "mihomo": {"path": "/version", "probe_host": "127.0.0.1"},
    "private-music-library": {"probe_host": "127.0.0.1"},
    "shadowbroker": {"probe_host": "127.0.0.1"},
    "uptime-kuma": {"probe_host": "127.0.0.1"},
    "wireguard": {"probe_host": "127.0.0.1"},
    "zigbee2mqtt": {"probe_host": "127.0.0.1"},
}

TCP_PROBE_HOST_OVERRIDES = {
    HOMENET_SERVER_IP: "127.0.0.1",
}

PROBE_KEY_ALIASES = {
    "adguard-ui": "adguard",
    "adguard-dns-udp": "adguard",
    "mihomo-dns": "mihomo",
    "mihomo-dns-udp": "mihomo",
    "mihomo-udp": "mihomo",
    "wg-easy": "wireguard",
    "wireguard-udp": "wireguard",
    "caddy-http": "caddy",
    "caddy-https": "caddy",
    "shadowbroker-api": "shadowbroker",
    "presence-receiver-tcp": "presence-receiver",
    "ha-go2rtc-api": "go2rtc",
    "ha-go2rtc-rtsp": "go2rtc",
}

MAC_STUDIO_PATHS = [
    {"name": "ethernet", "ip": os.getenv("MAC_STUDIO_ETHERNET_IP", "")},
    {"name": "wifi", "ip": os.getenv("MAC_STUDIO_WIFI_IP", "")},
]

mac_map: Dict[str, Dict[str, str]] = {}
ip_map: Dict[str, str] = {}
prev_wan: Tuple[int, int, float] | None = None
prev_device_bytes: Dict[str, Tuple[str, str, int, int, float]] = {}
prev_conn_bytes: Dict[str, Tuple[int, int, float]] = {}
prev_mihomo_traffic: Tuple[int, int, float] | None = None
history_samples: List[Dict] = []
health_lock = asyncio.Lock()

mac_re = re.compile(r"lladdr\s+([0-9a-f]{2}(?::[0-9a-f]{2}){5})", re.I)
assoc_mac_re = re.compile(r"\b[0-9a-f]{2}(?::[0-9a-f]{2}){5}\b", re.I)
mihomo_controller_re = re.compile(r"^\s*secret\s*:\s*(.*?)\s*$")
dns_query_re = re.compile(r"dnsmasq\[\d+\]: .*?query\[(?P<type>[^\]]+)\] (?P<host>\S+) from (?P<ip>\S+)")
ipv4_re = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
fake_ip_re = re.compile(r"\b198\.1[89]\.\d{1,3}\.\d{1,3}\b")
domain_re = re.compile(r"^(?=.{1,253}$)(?!-)[a-z0-9*_.-]+(?<!-)$", re.I)

ROUTING_POLICIES = {
    "DIRECT": {"provider": "ops-routing-direct", "label": "DIRECT"},
    "PROXY": {"provider": "ops-routing-proxy", "label": "PROXY"},
    "PROXY-JAPAN": {"provider": "ops-routing-japan", "label": "PROXY-JAPAN"},
    "AI-NODES": {"provider": "ops-routing-ai", "label": "AI-NODES"},
    "IPV6-NODES": {"provider": "ops-routing-ipv6", "label": "IPV6-NODES"},
}

ROUTING_DURATIONS = {
    "1h": 3600,
    "today": 24 * 3600,
    "7d": 7 * 24 * 3600,
    "forever": None,
}

KNOWN_MAC_NAMES = {}


def load_metadata() -> Dict:
    previous = STATE.get("metadata", {}) if isinstance(STATE.get("metadata"), dict) else {}
    if not HOMENET_PLAN_TOOL.exists():
        return {
            **previous,
            "ok": False,
            "error": f"{HOMENET_PLAN_TOOL} missing",
            "updated_at": time.time(),
        }
    try:
        result = subprocess.run(
            ["python", str(HOMENET_PLAN_TOOL), "metadata", "--instance", str(INSTANCE_DIR)],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=METADATA_TIMEOUT,
        )
    except Exception as e:
        add_error(f"homenet metadata failed: {type(e).__name__}: {e}")
        return {**previous, "ok": False, "error": f"{type(e).__name__}: {e}", "updated_at": time.time()}

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or f"exit {result.returncode}").strip()[:300]
        add_error(f"homenet metadata failed: {detail}")
        return {**previous, "ok": False, "error": detail, "updated_at": time.time()}

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        add_error(f"homenet metadata JSON failed: {e}")
        return {**previous, "ok": False, "error": f"JSONDecodeError: {e}", "updated_at": time.time()}

    if data.get("schema") != "homenet.metadata.v1":
        add_error(f"homenet metadata schema unexpected: {data.get('schema')}")
        return {**previous, "ok": False, "error": f"unexpected schema {data.get('schema')}", "updated_at": time.time()}

    return {**data, "ok": True, "updated_at": time.time()}


def metadata_instance(metadata: Dict) -> Dict:
    return {
        "ok": bool(metadata.get("ok")),
        "site": metadata.get("site") or {},
        "networks": metadata.get("networks") or {},
        "wifi": metadata.get("wifi") or {},
        "devices": metadata.get("devices") or [],
        "services": metadata.get("service_directory") or [],
        "updated_at": metadata.get("updated_at") or time.time(),
    }


def metadata_plan(metadata: Dict) -> Dict:
    return {
        "ok": bool(metadata.get("ok")),
        "schema": "homenet.plan.v1",
        "instance": metadata.get("instance") or {},
        "profile": metadata.get("profile") or "",
        "runtime_targets": metadata.get("runtime_targets") or {},
        "networks": metadata.get("networks") or {},
        "wifi": metadata.get("wifi") or {},
        "module_placement": metadata.get("module_placement") or [],
        "service_inventory": metadata.get("service_inventory") or {},
        "modules": metadata.get("module_plan") or [],
        "apply": metadata.get("apply") or {},
        "updated_at": metadata.get("updated_at") or time.time(),
    }


def metadata_blueprint(metadata: Dict) -> Dict:
    capabilities = []
    for item in metadata.get("capability_matrix") or []:
        if not isinstance(item, dict):
            continue
        status = item.get("current_status") or ""
        if status not in {"enabled", "fallback"}:
            continue
        capabilities.append({
            "id": item.get("id") or "",
            "title": item.get("title") or item.get("id") or "",
            "status": status,
            "required": bool(item.get("required")),
            "placement": item.get("current_placement") or item.get("fallback") or "",
            "fallback": item.get("fallback") or "",
        })

    services_by_category = defaultdict(int)
    for service in metadata.get("service_directory") or []:
        if isinstance(service, dict):
            services_by_category[service.get("category") or "other"] += 1

    return {
        "ok": bool(metadata.get("ok")),
        "schema": "homenet.blueprint.v1",
        "profile": metadata.get("profile") or "",
        "position": "HomeNet is a home network operations system, not only a proxy setup.",
        "problem": [
            "Domestic apps stay direct while foreign apps and AI services use Proxy rules.",
            "DNS, Proxy, DHCP, Wi-Fi, Tunnel, monitoring, and services share one operating model.",
            "Maintenance paths stay visible when normal DNS/Proxy/Wi-Fi is broken.",
        ],
        "provides": [
            "Instance Model",
            "Planner",
            "Read-only Checker",
            "Ops",
            "Metadata / Docs / Kuma / Artifacts",
        ],
        "non_goals": [
            "Not a consumer mesh replacement.",
            "Not a black-box VPN product.",
            "Not a promise to hide VPN/proxy usage from hostile apps.",
        ],
        "operational_questions": [
            {"question": "What should this network look like?", "surface": "instance files + blueprint/plan"},
            {"question": "What is actually running now?", "surface": "HomeNet live state + source dashboards"},
            {"question": "How does traffic move?", "surface": "Topology + DNS/Proxy/WireGuard/Tunnel evidence"},
            {"question": "Where should a person go?", "surface": "Service Directory + source-tool links"},
            {"question": "What would apply change?", "surface": "homenet artifacts"},
        ],
        "active_capabilities": capabilities,
        "service_summary": {
            "total": len(metadata.get("service_directory") or []),
            "by_category": dict(sorted(services_by_category.items())),
        },
        "source_of_truth": [
            {"area": "Gateway / DHCP / Firewall / Wi-Fi", "owner": "OpenWrt"},
            {"area": "DNS behavior", "owner": "AdGuard DNS or OpenWrt dnsmasq/mosdns"},
            {"area": "Proxy behavior", "owner": "Mihomo Proxy"},
            {"area": "Remote LAN access", "owner": "WireGuard"},
            {"area": "Selected HTTPS remote entries", "owner": "Cloudflare Tunnel / Caddy"},
            {"area": "Alerting and uptime history", "owner": "Uptime Kuma"},
            {"area": "Daily operations summary", "owner": "HomeNet Ops"},
            {"area": "Desired state", "owner": "HomeNet instance files"},
        ],
        "updated_at": metadata.get("updated_at") or time.time(),
    }


def metadata_ingress_entries(metadata: Dict) -> List[Dict]:
    rows = []
    for entry in metadata.get("remote_ingress") or []:
        if not isinstance(entry, dict):
            continue
        rows.append({
            "key": entry.get("id") or entry.get("name") or "",
            "name": entry.get("name") or entry.get("id") or "",
            "kind": entry.get("kind") or "external",
            "href": entry.get("href") or "",
            "target": entry.get("target") or "",
            "service_id": entry.get("service_id") or "",
            "status_source": entry.get("status_source") or "static",
            "status": "ok",
            "detail": "入口配置来自 homenet.metadata.v1；外网可达性由 Kuma/WireGuard/Cloudflare 负责告警",
        })
    return rows


def port_sort_value(port: Dict) -> Tuple[str, int, str, str]:
    raw_port = str(port.get("port", "0"))
    try:
        port_num = int(raw_port.split("-")[0])
    except ValueError:
        port_num = 0
    return (
        str(port.get("host", "")),
        port_num,
        str(port.get("proto", "")),
        str(port.get("service", "")),
    )


def instance_service_entries() -> List[Dict]:
    services = STATE.get("instance", {}).get("services", [])
    entries = []
    for service in services:
        if not isinstance(service, dict):
            continue
        key = str(service.get("id") or "")
        if not key:
            continue
        has_probe = has_instance_probe(key)
        entries.append({
            "key": key,
            "name": service.get("name") or key,
            "kind": service.get("category") or "other",
            "role": service.get("role") or "",
            "href": service.get("remote_url") or "",
            "local_href": service.get("local_url") or "",
            "status": "unknown" if has_probe else "tracked",
            "latency_ms": 0,
            "detail": service.get("notes") or f"{service.get('runtime', 'runtime')} · {service.get('host', '')}".strip(" ·"),
            "source": "instance",
        })
    return entries


def instance_port_overview() -> List[Dict]:
    rows = []
    ports = STATE.get("metadata", {}).get("port_inventory", [])
    for port in ports:
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

    return sorted(rows, key=port_sort_value)


def local_probe_url(service: Dict) -> str:
    key = str(service.get("id") or "")
    override = HTTP_PROBE_OVERRIDES.get(key, {})
    source_url = str(service.get("local_url") or "")
    if not source_url:
        return ""

    parsed = urlparse(source_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""

    host = str(override.get("probe_host") or parsed.hostname or "")
    port = str(override.get("probe_port") or parsed.port or "")
    netloc = f"{host}:{port}" if port else host
    path = str(override.get("path") or parsed.path or "/")
    if not path.startswith("/"):
        path = f"/{path}"
    return urlunparse((parsed.scheme, netloc, path, "", parsed.query if not override.get("path") else "", parsed.fragment))


def instance_http_targets() -> List[Dict]:
    targets = []
    for service in STATE.get("instance", {}).get("services", []):
        if not isinstance(service, dict):
            continue
        url = local_probe_url(service)
        if not url:
            continue
        key = str(service.get("id") or "")
        targets.append({
            "key": key,
            "name": service.get("name") or key,
            "kind": service.get("category") or "other",
            "url": url,
            "href": service.get("remote_url") or "",
            "local_href": service.get("local_url") or "",
            "role": service.get("role") or "",
        })
    return targets


def instance_tcp_targets() -> List[Dict]:
    targets = []
    for port in instance_port_overview():
        proto = str(port.get("proto") or "")
        if "tcp" not in proto:
            continue
        service_key = str(port.get("service_key") or "")
        host = str(port.get("host") or "")
        targets.append({
            "key": service_key,
            "name": port.get("service") or service_key,
            "kind": "port",
            "host": TCP_PROBE_HOST_OVERRIDES.get(host, host),
            "port": int(str(port.get("port") or "0").split("-")[0]),
            "role": port.get("note") or "",
        })
    return targets


def instance_udp_targets() -> List[Dict]:
    by_service: Dict[str, Dict] = {}
    for port in instance_port_overview():
        proto = str(port.get("proto") or "")
        if "udp" not in proto:
            continue
        service_key = str(port.get("service_key") or "")
        row = by_service.setdefault(service_key, {
            "key": service_key,
            "name": port.get("service") or service_key,
            "kind": "udp-entry",
            "ports": [],
            "role": port.get("note") or "",
        })
        try:
            row["ports"].append(int(str(port.get("port") or "0").split("-")[0]))
        except ValueError:
            continue
    return list(by_service.values())


def has_instance_probe(service_id: str) -> bool:
    normalized = normalize_service_key(service_id)
    for target in [*instance_http_targets(), *instance_tcp_targets(), *instance_udp_targets()]:
        if normalize_service_key(str(target.get("key") or "")) == normalized:
            return True
    return False


def normalize_service_key(key: str) -> str:
    return PROBE_KEY_ALIASES.get(key, key)


def normalize_probe_result(row: Dict) -> Dict:
    key = normalize_service_key(str(row.get("key") or ""))
    if key == row.get("key"):
        return row
    return {**row, "key": key}


def service_by_key(key: str) -> Dict:
    normalized = normalize_service_key(key)
    for service in STATE.get("home_services", []):
        if normalize_service_key(str(service.get("key") or "")) == normalized:
            return service
    return {}


def service_status(key: str) -> str:
    return str(service_by_key(key).get("status") or "unknown")


def status_is_ok(status: str) -> bool:
    return status in {"ok", "tracked"}


def worst_status(statuses: List[str]) -> str:
    rank = {"bad": 4, "down": 4, "warn": 3, "unknown": 2, "tracked": 1, "ok": 0}
    return max(statuses or ["unknown"], key=lambda item: rank.get(item or "unknown", 2))


def is_ipv4(ip: str) -> bool:
    return "." in ip and ":" not in ip


def load_mihomo_secret() -> str:
    if MIHOMO_CONTROLLER_CREDENTIAL:
        return MIHOMO_CONTROLLER_CREDENTIAL
    try:
        with open(MIHOMO_CONFIG, "r", encoding="utf-8") as f:
            for line in f:
                match = mihomo_controller_re.match(line)
                if not match:
                    continue
                value = match.group(1).strip()
                if not value:
                    return ""
                if value[0] in ("'", '"') and value[-1:] == value[0]:
                    value = value[1:-1]
                return value
    except OSError:
        return ""
    return ""


def atomic_write_text(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    tmp.replace(path)


def write_text_preserve_owner(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(body)


def normalize_routing_target(raw: str) -> Dict[str, str]:
    value = (raw or "").strip()
    if not value:
        raise ValueError("empty target")
    if "://" not in value and "/" in value:
        value = value.split("/", 1)[0]
    parsed = urlparse(value if "://" in value else f"//{value}")
    host = (parsed.hostname or value).strip().lower().rstrip(".")
    if not host:
        raise ValueError("empty host")
    if ipv4_re.fullmatch(host):
        return {"kind": "ip", "value": host, "rule": f"IP-CIDR,{host}/32,no-resolve"}
    if ":" in host:
        return {"kind": "ip6", "value": host, "rule": f"IP-CIDR6,{host}/128,no-resolve"}
    host = host.replace("www.", "", 1)
    if host.startswith("*."):
        host = host[2:]
    if not domain_re.fullmatch(host) or "." not in host:
        raise ValueError("target must be a domain name or IP address")
    return {"kind": "domain", "value": host, "rule": f"DOMAIN-SUFFIX,{host}"}


def load_routing_store() -> Dict:
    try:
        data = json.loads(ROUTING_RULES_STORE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    entries = data.get("entries") if isinstance(data, dict) else []
    if not isinstance(entries, list):
        entries = []
    permanent_candidates = data.get("permanent_candidates") if isinstance(data, dict) else []
    if not isinstance(permanent_candidates, list):
        permanent_candidates = []
    return {
        "entries": [item for item in entries if isinstance(item, dict)],
        "permanent_candidates": [item for item in permanent_candidates if isinstance(item, dict)],
    }


def routing_permanent_candidates(data: Dict | None = None) -> List[Dict]:
    data = data or load_routing_store()
    candidates = data.get("permanent_candidates") or []
    return sorted(candidates, key=lambda item: (item.get("policy", ""), item.get("value", "")))


def save_routing_permanent_candidate(item: Dict) -> Dict:
    data = load_routing_store()
    candidate = {
        "schema": "homenet.routing-permanent-candidate.v1",
        "id": f"permanent-pending:{item.get('policy')}:{item.get('value')}",
        "created_at": time.time(),
        "status": "pending",
        "policy": item.get("policy"),
        "kind": item.get("kind"),
        "value": item.get("value"),
        "rule": item.get("rule"),
        "source": item.get("id") or "manual",
    }
    candidates = [
        existing for existing in routing_permanent_candidates(data)
        if existing.get("id") != candidate["id"]
    ]
    candidates.append(candidate)
    save_routing_store({**data, "permanent_candidates": candidates})
    return candidate


def save_routing_store(data: Dict) -> None:
    payload = {
        "schema": "homenet.routing-rules.v1",
        "updated_at": time.time(),
        "entries": sorted(data.get("entries") or [], key=lambda item: (item.get("scope", ""), item.get("policy", ""), item.get("value", ""))),
        "permanent_candidates": sorted(data.get("permanent_candidates") or [], key=lambda item: (item.get("policy", ""), item.get("value", ""))),
    }
    write_text_preserve_owner(ROUTING_RULES_STORE, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def active_routing_entries(data: Dict | None = None) -> List[Dict]:
    now = time.time()
    data = data or load_routing_store()
    active = []
    changed = False
    for item in data.get("entries") or []:
        expires_at = item.get("expires_at")
        if expires_at and float(expires_at) <= now:
            changed = True
            continue
        active.append(item)
    if changed:
        save_routing_store({"entries": active})
    return active


def rules_yaml(rules: List[str]) -> str:
    if not rules:
        return "payload: []\n"
    return "payload:\n" + "".join(f"  - {rule}\n" for rule in sorted(set(rules)))


def read_payload_rules(path: Path) -> List[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    rules = []
    for line in text.splitlines():
        match = re.match(r"^\s*-\s*(.+?)\s*$", line)
        if match:
            rules.append(match.group(1).strip())
    return rules


def remove_payload_rule(path: Path, rule: str) -> None:
    rules = [item for item in read_payload_rules(path) if item != rule]
    atomic_write_text(path, rules_yaml(rules))


def write_routing_rule_files(entries: List[Dict]) -> None:
    policy_rules = {meta["provider"]: [] for meta in ROUTING_POLICIES.values()}
    for item in entries:
        policy = item.get("policy")
        meta = ROUTING_POLICIES.get(str(policy))
        if not meta:
            continue
        rule = str(item.get("rule") or "")
        if not rule:
            continue
        policy_rules[meta["provider"]].append(rule)

    for provider, rules in policy_rules.items():
        write_text_preserve_owner(ROUTING_RULE_DIR / f"{provider}.yaml", rules_yaml(rules))


def runtime_provider(provider: str) -> Dict:
    return {
        "type": "file",
        "behavior": "classical",
        "format": "yaml",
        "path": f"./rules/{provider}.yaml",
    }


def routing_rule_lines() -> List[str]:
    return [
        f"RULE-SET,{ROUTING_POLICIES['DIRECT']['provider']},DIRECT",
        f"RULE-SET,{ROUTING_POLICIES['PROXY-JAPAN']['provider']},PROXY-JAPAN",
        f"RULE-SET,{ROUTING_POLICIES['AI-NODES']['provider']},AI-NODES",
        f"RULE-SET,{ROUTING_POLICIES['IPV6-NODES']['provider']},IPV6-NODES",
        f"RULE-SET,{ROUTING_POLICIES['PROXY']['provider']},PROXY",
    ]


def ensure_routing_overlay() -> None:
    if not MIHOMO_CONFIG_WRITE.exists():
        return
    try:
        config = yaml.safe_load(MIHOMO_CONFIG_WRITE.read_text(encoding="utf-8")) or {}
    except Exception as e:
        raise RuntimeError(f"cannot parse Mihomo config: {e}") from e
    if not isinstance(config, dict):
        raise RuntimeError("Mihomo config root is not a map")

    providers = config.setdefault("rule-providers", {})
    if not isinstance(providers, dict):
        raise RuntimeError("Mihomo rule-providers is not a map")
    for meta in ROUTING_POLICIES.values():
        provider = meta["provider"]
        providers[provider] = runtime_provider(provider)

    rules = config.setdefault("rules", [])
    if not isinstance(rules, list):
        raise RuntimeError("Mihomo rules is not a list")
    overlay_rules = routing_rule_lines()
    rules = [rule for rule in rules if rule not in overlay_rules]
    config["rules"] = [*overlay_rules, *rules]

    write_text_preserve_owner(MIHOMO_CONFIG_WRITE, yaml.safe_dump(config, allow_unicode=True, sort_keys=False))


async def reload_mihomo_config() -> Tuple[bool, str]:
    secret = load_mihomo_secret()
    headers = {"Authorization": f"Bearer {secret}"} if secret else {}
    timeout = aiohttp.ClientTimeout(total=5)
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        async with session.put(f"{MIHOMO_URL}/configs", json={"path": MIHOMO_RUNTIME_CONFIG}) as resp:
            detail = await resp.text()
            return resp.status < 300, detail[:240]


async def apply_routing_rules() -> Tuple[bool, str]:
    entries = active_routing_entries()
    write_routing_rule_files(entries)
    try:
        ensure_routing_overlay()
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    try:
        return await reload_mihomo_config()
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def ssh_cmd(remote_cmd: str, timeout: float = 5.0) -> List[str]:
    return ["ssh", "-F", "/dev/null", *SSH_OPTS, f"{OPENWRT_USER}@{OPENWRT_HOST}", remote_cmd]


def clean_ssh_stderr(err: str) -> str:
    lines = []
    skip_next = False
    for line in err.splitlines():
        text = line.strip()
        if not text:
            continue
        if skip_next:
            skip_next = False
            continue
        if text.startswith("** WARNING: connection is not using a post-quantum key exchange algorithm."):
            skip_next = True
            continue
        if "store now, decrypt later" in text or "openssh.com/pq.html" in text:
            continue
        lines.append(line)
    return "\n".join(lines).strip()


async def run_cmd(cmd: List[str], timeout: float = 5.0) -> Tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return 124, "", "timeout"
    return proc.returncode, out.decode(errors="replace"), err.decode(errors="replace")


async def refresh_dhcp_map():
    global mac_map, ip_map
    remote = "cat /tmp/dhcp.leases 2>/dev/null; echo __NEIGH__; ip neigh show 2>/dev/null; ip -6 neigh show 2>/dev/null"
    code, out, err = await run_cmd(ssh_cmd(remote), timeout=5)
    if code != 0:
        add_error(f"OpenWrt device map SSH failed: {err.strip() or code}")
        return
    new_map = {}
    new_ip_map = {}
    leases, _, neigh = out.partition("__NEIGH__")
    for line in leases.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            mac = parts[1].lower()
            ip = parts[2]
            name = parts[3] if parts[3] != "*" else "unknown"
            new_map[mac] = {"mac": mac, "ip": ip, "name": name}
            new_ip_map[ip] = mac
    for line in neigh.splitlines():
        parts = line.split()
        if not parts:
            continue
        ip = parts[0]
        mm = mac_re.search(line)
        if not mm:
            continue
        mac = mm.group(1).lower()
        if mac not in new_map:
            new_map[mac] = {"mac": mac, "ip": ip, "name": KNOWN_MAC_NAMES.get(mac, "unknown")}
        elif ":" in ip:
            new_map[mac]["ipv6"] = ip
        # Keep DHCP lease ownership for IPv4 clients behind a bridge/AP.
        # Some APs reply in ARP/neighbor table with the bridge MAC, while
        # dnsmasq still knows the real client MAC from DHCP.
        if not (is_ipv4(ip) and ip in new_ip_map and new_ip_map[ip] != mac):
            new_ip_map[ip] = mac
    if new_map or new_ip_map:
        mac_map = new_map
        ip_map = new_ip_map


def add_error(msg: str):
    now = time.strftime("%H:%M:%S")
    STATE["errors"] = ([f"{now} {msg}"] + STATE.get("errors", []))[:8]
    STATE["error_events"] = ([f"{now} {msg}"] + STATE.get("error_events", []))[:24]


def recent_errors() -> List[str]:
    now = time.time()
    today = time.localtime(now)
    rows = []
    for item in STATE.get("errors", []):
        text = str(item)
        first = text.split(None, 1)[0] if text else ""
        try:
            hour, minute, second = [int(part) for part in first.split(":")]
            candidate = time.mktime((
                today.tm_year,
                today.tm_mon,
                today.tm_mday,
                hour,
                minute,
                second,
                today.tm_wday,
                today.tm_yday,
                today.tm_isdst,
            ))
            if candidate > now + 60:
                candidate -= 86400
            if now - candidate <= ERROR_TTL:
                rows.append(text)
        except (TypeError, ValueError):
            rows.append(text)
    return rows


def parse_log_time(line: str) -> float:
    # OpenWrt logread usually starts with "Wed May 20 07:20:31 2026".
    parts = line.split(None, 5)
    if len(parts) < 5:
        return time.time()
    text = " ".join(parts[:5])
    try:
        return time.mktime(time.strptime(text, "%a %b %d %H:%M:%S %Y"))
    except ValueError:
        return time.time()


def device_label(row: Dict[str, str]) -> str:
    name = row.get("name") or ""
    ip = row.get("ip") or ""
    mac = row.get("mac") or ""
    if name and name != "unknown":
        return name
    return ip or mac or "unknown"


def device_for_ip(ip: str) -> Dict[str, str]:
    mac = ip_map.get(ip, "")
    info = mac_map.get(mac, {})
    return {
        "ip": ip,
        "mac": mac,
        "name": info.get("name") or "",
    }


def health_check(status: str, title: str, detail: str) -> Dict[str, str]:
    return {"status": status, "title": title, "detail": detail}


def parse_ipv4s(text: str) -> List[str]:
    ips = []
    for ip in ipv4_re.findall(text):
        parts = [int(p) for p in ip.split(".") if p.isdigit()]
        if len(parts) == 4 and all(0 <= p <= 255 for p in parts) and ip not in ips:
            ips.append(ip)
    return ips


def parse_uci_lines(text: str) -> Dict[str, str]:
    rows = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
            value = value[1:-1]
        rows[key.strip()] = value
    return rows


def parse_dhcp_dns(option_text: str) -> str:
    for chunk in re.split(r"\s+", option_text.replace("'", " ").strip()):
        chunk = chunk.strip()
        if not chunk.startswith("6,"):
            continue
        return ",".join(parse_ipv4s(chunk))
    return ""


def ok_check(title: str, ok: bool, detail: str, warn: bool = False) -> Dict[str, str]:
    return health_check("ok" if ok else ("warn" if warn else "bad"), title, detail)


async def refresh_health_checks():
    checks = []

    try:
        with open(ADGUARD_DOMESTIC_FILE, "r", encoding="utf-8") as f:
            text = f.read()
        has_default = "127.0.0.1:1053" in text
        has_domestic = "[/snssdk.com/]" in text or "snssdk.com" in text
        if has_default and has_domestic:
            checks.append(health_check("ok", "AdGuard 国内分流表", "已挂载，国内域名定向国内 DNS，默认回 Mihomo DNS"))
        else:
            checks.append(health_check("warn", "AdGuard 国内分流表", "文件存在，但关键规则或默认上游不完整"))
    except OSError as e:
        checks.append(health_check("warn", "AdGuard 国内分流表", f"Live 容器未读到 {ADGUARD_DOMESTIC_FILE}: {e.strerror}"))

    dns_cmd = (
        "echo __DOMESTIC__; nslookup aweme.snssdk.com 127.0.0.1 2>&1; "
        "echo __FOREIGN__; nslookup github.com 127.0.0.1 2>&1"
    )
    code, out, err = await run_cmd(ssh_cmd(dns_cmd), timeout=6)
    domestic_ips: List[str] = []
    if code != 0:
        checks.append(health_check("bad", "OpenWrt DNS 探测", err.strip() or f"exit {code}"))
    else:
        _, _, rest = out.partition("__DOMESTIC__")
        domestic_text, _, foreign_text = rest.partition("__FOREIGN__")
        domestic_ips = [ip for ip in parse_ipv4s(domestic_text) if ip != "127.0.0.1"]
        foreign_ips = [ip for ip in parse_ipv4s(foreign_text) if ip != "127.0.0.1"]
        domestic_fake = any(fake_ip_re.match(ip) for ip in domestic_ips)
        foreign_fake = any(fake_ip_re.match(ip) for ip in foreign_ips)

        if domestic_ips and not domestic_fake:
            checks.append(health_check("ok", "国内域名解析", f"aweme.snssdk.com -> {', '.join(domestic_ips[:3])}"))
        elif domestic_fake:
            checks.append(health_check("bad", "国内域名解析", f"aweme.snssdk.com 仍返回 fake-ip: {', '.join(domestic_ips[:3])}"))
        else:
            checks.append(health_check("warn", "国内域名解析", "aweme.snssdk.com 没拿到 IPv4 结果"))

        if foreign_fake:
            checks.append(health_check("ok", "海外域名解析", f"github.com -> {', '.join(foreign_ips[:3])}"))
        elif foreign_ips:
            checks.append(health_check("warn", "海外域名解析", f"github.com 未返回 fake-ip: {', '.join(foreign_ips[:3])}"))
        else:
            checks.append(health_check("warn", "海外域名解析", "github.com 没拿到 IPv4 结果"))

    cn_ip = next((ip for ip in domestic_ips if not fake_ip_re.match(ip)), "")
    if cn_ip:
        code, out, err = await run_cmd(ssh_cmd(f"ipset test MIHOMO_CN4 {cn_ip} >/dev/null 2>&1 && echo yes || echo no"), timeout=4)
        if code == 0 and out.strip() == "yes":
            checks.append(health_check("ok", "OpenWrt 国内 IP 绕过", f"{cn_ip} 命中 MIHOMO_CN4，会绕过 Pi"))
        elif code == 0:
            checks.append(health_check("warn", "OpenWrt 国内 IP 绕过", f"{cn_ip} 未命中 MIHOMO_CN4"))
        else:
            checks.append(health_check("warn", "OpenWrt 国内 IP 绕过", err.strip() or f"ipset test exit {code}"))

    ops = STATE.get("ops_network", {}) if isinstance(STATE.get("ops_network"), dict) else {}
    for item in ops.get("checks", []):
        checks.append(health_check(item.get("status", "unknown"), f"Maintenance Wi-Fi：{item.get('title', 'check')}", item.get("detail", "")))

    STATE["health"] = {"updated_at": time.time(), "checks": checks}


async def ensure_health_checks():
    now = time.time()
    if now - float(STATE.get("health", {}).get("updated_at", 0) or 0) < HEALTH_INTERVAL:
        return
    async with health_lock:
        now = time.time()
        if now - float(STATE.get("health", {}).get("updated_at", 0) or 0) < HEALTH_INTERVAL:
            return
        await refresh_health_checks()


async def read_dns_queries():
    remote = "logread | grep 'dnsmasq.*query\\[' | tail -300"
    code, out, err = await run_cmd(ssh_cmd(remote), timeout=5)
    if code not in (0, 1):
        add_error(f"dns query log read failed: {err.strip() or code}")
        return
    rows = []
    seen = set()
    now = time.time()
    for line in reversed(out.splitlines()):
        match = dns_query_re.search(line)
        if not match:
            continue
        ip = match.group("ip")
        host = match.group("host").rstrip(".")
        qtype = match.group("type")
        ts = parse_log_time(line)
        mac = ip_map.get(ip)
        info = mac_map.get(mac or "", {})
        key = (ip, host, qtype)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "time": ts,
            "age_seconds": max(0, int(now - ts)),
            "ip": ip,
            "mac": mac or "",
            "name": info.get("name") or "",
            "host": host,
            "type": qtype,
        })
        if len(rows) >= 80:
            break
    STATE["dns_queries"] = rows

    recent = [r for r in rows if r.get("age_seconds", 999999) <= 300]
    by_device = defaultdict(lambda: {"count": 0, "hosts": defaultdict(int), "row": {}})
    by_host = defaultdict(lambda: {"count": 0, "devices": defaultdict(int)})
    for row in recent:
        dev = device_label(row)
        host = row.get("host") or "unknown"
        by_device[dev]["count"] += 1
        by_device[dev]["hosts"][host] += 1
        by_device[dev]["row"] = row
        by_host[host]["count"] += 1
        by_host[host]["devices"][dev] += 1
    STATE["dns_top_devices"] = [
        {
            "device": dev,
            "ip": data["row"].get("ip", ""),
            "count": data["count"],
            "top_hosts": [h for h, _ in sorted(data["hosts"].items(), key=lambda x: (-x[1], x[0]))[:5]],
        }
        for dev, data in sorted(by_device.items(), key=lambda x: (-x[1]["count"], x[0]))[:12]
    ]
    STATE["dns_top_hosts"] = [
        {
            "host": host,
            "count": data["count"],
            "devices": [d for d, _ in sorted(data["devices"].items(), key=lambda x: (-x[1], x[0]))[:5]],
        }
        for host, data in sorted(by_host.items(), key=lambda x: (-x[1]["count"], x[0]))[:20]
    ]


async def read_wan_counters():
    global prev_wan
    cmd = f"cat /sys/class/net/{WAN_IF}/statistics/rx_bytes /sys/class/net/{WAN_IF}/statistics/tx_bytes 2>/dev/null"
    code, out, err = await run_cmd(ssh_cmd(cmd), timeout=5)
    if code != 0:
        clean_err = clean_ssh_stderr(err)
        add_error(f"WAN counter failed: {clean_err or code}")
        return
    nums = [int(x) for x in out.split() if x.strip().isdigit()]
    if len(nums) < 2:
        add_error(f"WAN counter empty for {WAN_IF}")
        return
    rx, tx = nums[0], nums[1]
    now = time.time()
    down = up = 0.0
    if prev_wan:
        prx, ptx, pts = prev_wan
        dt = max(now - pts, 0.001)
        down = max(rx - prx, 0) * 8 / 1_000_000 / dt
        up = max(tx - ptx, 0) * 8 / 1_000_000 / dt
    prev_wan = (rx, tx, now)
    STATE["wan"] = {"down_mbps": down, "up_mbps": up, "rx_bytes": rx, "tx_bytes": tx, "if": WAN_IF}


def parse_conntrack_line(line: str) -> Tuple[str, str, int, int] | None:
    parts = line.split()
    if len(parts) < 8:
        return None
    family = parts[0]
    proto = parts[2]
    srcs = [p[4:] for p in parts if p.startswith("src=")]
    dsts = [p[4:] for p in parts if p.startswith("dst=")]
    sports = [p[6:] for p in parts if p.startswith("sport=")]
    dports = [p[6:] for p in parts if p.startswith("dport=")]
    byte_values = [int(p[6:]) for p in parts if p.startswith("bytes=") and p[6:].isdigit()]
    if len(srcs) < 2 or len(dsts) < 2 or len(byte_values) < 2:
        return None
    sport = sports[0] if sports else ""
    dport = dports[0] if dports else ""
    key = "|".join([family, proto, srcs[0], dsts[0], sport, dport, srcs[1], dsts[1]])
    return key, srcs[0], byte_values[0], byte_values[1]


async def read_device_counters():
    global prev_device_bytes
    code, out, err = await run_cmd(ssh_cmd("cat /proc/net/nf_conntrack 2>/dev/null || cat /proc/net/ip_conntrack 2>/dev/null || true"), timeout=5)
    if code != 0:
        add_error(f"conntrack read failed: {err.strip() or code}")
        return
    now = time.time()
    current = {}
    rates = defaultdict(lambda: [0.0, 0.0])
    for line in out.splitlines():
        parsed = parse_conntrack_line(line)
        if not parsed:
            continue
        key, source_ip, upload_bytes, download_bytes = parsed
        mac = ip_map.get(source_ip)
        if not mac:
            continue
        current[key] = (mac, source_ip, upload_bytes, download_bytes, now)
        if key not in prev_device_bytes:
            continue
        prev_mac, _, prev_up, prev_down, prev_ts = prev_device_bytes[key]
        if prev_mac != mac:
            continue
        dt = max(now - prev_ts, 0.001)
        rates[mac][0] += max(upload_bytes - prev_up, 0) * 8 / 1_000_000 / dt
        rates[mac][1] += max(download_bytes - prev_down, 0) * 8 / 1_000_000 / dt
    prev_device_bytes = current

    devices = []
    for mac, (up, down) in rates.items():
        if up <= 0.01 and down <= 0.01:
            continue
        info = mac_map.get(mac, {"mac": mac, "ip": "", "name": "unknown"})
        devices.append({"mac": mac, "ip": info.get("ip") or info.get("ipv6", ""), "name": info.get("name", ""), "up_mbps": up, "down_mbps": down})
    STATE["devices"] = sorted(
        devices,
        key=lambda x: ((x.get("name") or "unknown").lower(), x.get("ip") or "", x.get("mac") or ""),
    )[:100]


async def read_mihomo():
    global prev_conn_bytes, prev_mihomo_traffic
    controller_credential = load_mihomo_secret()
    headers = {"Authorization": f"Bearer {controller_credential}"} if controller_credential else {}
    timeout = aiohttp.ClientTimeout(total=4)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        # Total mihomo traffic, if endpoint is available as streaming only this may fail silently.
        try:
            async with session.get(f"{MIHOMO_URL}/traffic", headers=headers) as resp:
                text = await resp.content.readline()
                if text:
                    obj = json.loads(text.decode())
                    up_bps = float(obj.get("up", 0))
                    down_bps = float(obj.get("down", 0))
                    STATE["mihomo"] = {"up_mbps": up_bps * 8 / 1_000_000, "down_mbps": down_bps * 8 / 1_000_000}
        except Exception:
            pass

        try:
            async with session.get(f"{MIHOMO_URL}/connections", headers=headers) as resp:
                if resp.status != 200:
                    add_error(f"mihomo /connections HTTP {resp.status}")
                    return
                data = await resp.json()
        except Exception as e:
            add_error(f"mihomo /connections failed: {e}")
            return

    now = time.time()
    domain_rates = defaultdict(lambda: [0.0, 0.0, 0, set(), set()])  # up, down, count, rules, chains
    route_rates = defaultdict(lambda: [0.0, 0.0, 0, set()])
    conn_rows = []
    current = {}
    connections = data.get("connections") or []
    for c in connections:
        cid = c.get("id") or f"{c.get('start')}:{c.get('metadata',{}).get('sourceIP')}:{c.get('metadata',{}).get('destinationIP')}:{c.get('metadata',{}).get('destinationPort')}"
        upload = int(c.get("upload", 0) or 0)
        download = int(c.get("download", 0) or 0)
        current[cid] = (upload, download, now)
        meta = c.get("metadata") or {}
        host = meta.get("host") or meta.get("destinationIP") or "unknown"
        source_ip = meta.get("sourceIP") or ""
        rule = c.get("rule") or ""
        rule_payload = c.get("rulePayload") or ""
        rule_label = f"{rule}({rule_payload})" if rule and rule_payload else (rule or rule_payload)
        chains = c.get("chains") or []
        chain = " / ".join(chains) if isinstance(chains, list) else str(chains)
        up_mbps = down_mbps = 0.0
        if cid in prev_conn_bytes:
            pu, pd, pts = prev_conn_bytes[cid]
            dt = max(now - pts, 0.001)
            up_mbps = max(upload - pu, 0) * 8 / 1_000_000 / dt
            down_mbps = max(download - pd, 0) * 8 / 1_000_000 / dt
        if up_mbps > 0.01 or down_mbps > 0.01:
            dev = device_for_ip(source_ip)
            row = {
                "host": host,
                "source_ip": source_ip,
                "source_mac": dev.get("mac", ""),
                "source_name": dev.get("name", ""),
                "up_mbps": up_mbps,
                "down_mbps": down_mbps,
                "rule": rule_label,
                "chain": chain,
            }
            conn_rows.append(row)
            dr = domain_rates[host]
            dr[0] += up_mbps
            dr[1] += down_mbps
            dr[2] += 1
            if rule_label: dr[3].add(str(rule_label))
            if chain: dr[4].add(chain)
            route_key = chain or "unknown"
            rr = route_rates[route_key]
            rr[0] += up_mbps
            rr[1] += down_mbps
            rr[2] += 1
            if rule_label:
                rr[3].add(str(rule_label))
    prev_conn_bytes = current
    domains = []
    for host, (up, down, count, rules, chains) in domain_rates.items():
        domains.append({"host": host, "up_mbps": up, "down_mbps": down, "connections": count, "rule": ", ".join(sorted(rules))[:80], "chain": ", ".join(sorted(chains))[:120]})
    STATE["domains"] = sorted(domains, key=lambda x: (x.get("host") or "").lower())[:80]
    STATE["connections"] = sorted(conn_rows, key=lambda x: ((x.get("host") or "").lower(), x.get("source_ip") or ""))[:100]
    STATE["route_summary"] = [
        {
            "chain": chain,
            "up_mbps": up,
            "down_mbps": down,
            "connections": count,
            "rules": ", ".join(sorted(rules))[:120],
        }
        for chain, (up, down, count, rules) in sorted(route_rates.items(), key=lambda x: (-(x[1][0] + x[1][1]), x[0]))[:12]
    ]


def build_port_overview() -> List[Dict]:
    return instance_port_overview()


def attach_ports_to_services(services: List[Dict], ports: List[Dict]) -> List[Dict]:
    ports_by_service: Dict[str, List[Dict]] = {}
    for port in ports:
        service_key = port.get("service_key")
        if not service_key:
            continue
        public_port = {k: v for k, v in port.items() if k != "service_key"}
        ports_by_service.setdefault(service_key, []).append(public_port)

    for service in services:
        service["ports"] = ports_by_service.get(service.get("key", ""), [])
    return services


def service_severity(status: str) -> int:
    return {
        "bad": 4,
        "down": 4,
        "warn": 3,
        "unknown": 2,
        "tracked": 1,
        "ok": 0,
    }.get(status or "unknown", 2)


def merge_services_by_key(services: List[Dict]) -> List[Dict]:
    merged: Dict[str, Dict] = {}
    order: List[str] = []
    for service in services:
        key = service.get("key") or f"{service.get('kind', 'other')}:{service.get('name', '')}"
        if key not in merged:
            merged[key] = dict(service)
            order.append(key)
            continue
        current = merged[key]
        for field in ("href", "local_href", "role", "kind", "name", "detail"):
            if not current.get(field) and service.get(field):
                current[field] = service[field]
        current_status = current.get("status", "")
        incoming_status = service.get("status", "")
        live_result_replaces_placeholder = current_status in ("unknown", "tracked", "") and incoming_status not in ("unknown", "tracked", "")
        incoming_is_worse = service_severity(incoming_status) > service_severity(current_status)
        if live_result_replaces_placeholder or incoming_is_worse:
            current["status"] = service.get("status")
            current["latency_ms"] = service.get("latency_ms", current.get("latency_ms", 0))
            current["detail"] = service.get("detail", current.get("detail", ""))
    return [merged[key] for key in order]


async def tcp_service_probe(target: Dict) -> Dict:
    started = time.time()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(target["host"], int(target["port"])),
            timeout=1.2,
        )
        writer.close()
        await writer.wait_closed()
        latency_ms = round((time.time() - started) * 1000)
        status = "ok"
        detail = f"tcp/{target['port']} open"
    except Exception as e:
        latency_ms = round((time.time() - started) * 1000)
        status = "bad"
        detail = f"tcp/{target['port']} {type(e).__name__}"
    return {
        "key": normalize_service_key(target["key"]),
        "name": target["name"],
        "kind": target["kind"],
        "role": target["role"],
        "href": target.get("href", ""),
        "local_href": target.get("local_href", ""),
        "status": status,
        "latency_ms": latency_ms,
        "detail": detail,
    }


def parse_proc_udp_ports() -> set[int]:
    ports: set[int] = set()
    for path in ("/proc/net/udp", "/proc/net/udp6"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()[1:]
        except OSError:
            continue
        for line in lines:
            parts = line.split()
            if len(parts) < 2:
                continue
            local = parts[1]
            if ":" not in local:
                continue
            _, port_hex = local.rsplit(":", 1)
            try:
                ports.add(int(port_hex, 16))
            except ValueError:
                continue
    return ports


async def udp_service_probe(target: Dict, listening_ports: set[int]) -> Dict:
    expected_ports = [int(port) for port in target.get("ports", [])]
    open_ports = [port for port in expected_ports if port in listening_ports]
    missing_ports = [port for port in expected_ports if port not in listening_ports]
    status = "ok" if expected_ports and not missing_ports else "bad"
    detail = (
        f"udp/{', udp/'.join(str(port) for port in open_ports)} listening"
        if status == "ok"
        else f"missing udp/{', udp/'.join(str(port) for port in missing_ports)}"
    )
    return {
        "key": normalize_service_key(target["key"]),
        "name": target["name"],
        "kind": target["kind"],
        "role": target["role"],
        "href": target.get("href", ""),
        "local_href": target.get("local_href", ""),
        "status": status,
        "latency_ms": 0,
        "detail": detail,
    }


async def http_service_probe(session: aiohttp.ClientSession, target: Dict) -> Dict:
    started = time.time()
    try:
        async with session.get(target["url"], allow_redirects=False) as resp:
            await resp.read()
            latency_ms = round((time.time() - started) * 1000)
            if resp.status < 400 or resp.status in (401, 403):
                status = "ok"
            elif resp.status < 500:
                status = "warn"
            else:
                status = "bad"
            detail = f"HTTP {resp.status}"
    except Exception as e:
        latency_ms = round((time.time() - started) * 1000)
        status = "bad"
        detail = f"{type(e).__name__}"
    return {
        "key": normalize_service_key(target["key"]),
        "name": target["name"],
        "kind": target["kind"],
        "role": target["role"],
        "href": target.get("href", ""),
        "local_href": target.get("local_href", ""),
        "status": status,
        "latency_ms": latency_ms,
        "detail": detail,
    }


async def refresh_home_services():
    metadata = load_metadata()
    STATE["metadata"] = metadata
    STATE["instance"] = metadata_instance(metadata)
    STATE["plan"] = metadata_plan(metadata)
    STATE["blueprint"] = metadata_blueprint(metadata)
    timeout = aiohttp.ClientTimeout(total=2.2)
    udp_ports = parse_proc_udp_ports()
    http_targets = instance_http_targets()
    tcp_targets = instance_tcp_targets()
    udp_targets = instance_udp_targets()
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(timeout=timeout, headers={"User-Agent": "HomeNetOps/1.0"}, connector=connector) as session:
        results = await asyncio.gather(
            *(http_service_probe(session, target) for target in http_targets),
            *(tcp_service_probe(target) for target in tcp_targets),
            *(udp_service_probe(target, udp_ports) for target in udp_targets),
            return_exceptions=True,
        )
    services = instance_service_entries()
    for result in results:
        if isinstance(result, Exception):
            services.append({
                "key": "probe-error",
                "name": "Probe error",
                "kind": "control-core",
                "role": "service probe",
                "status": "bad",
                "latency_ms": 0,
                "detail": f"{type(result).__name__}: {result}",
            })
        else:
            services.append(normalize_probe_result(result))
    ports = build_port_overview()
    services = merge_services_by_key(services)
    STATE["home_services"] = sorted(attach_ports_to_services(services, ports), key=lambda x: (x.get("kind", ""), x.get("name", "")))
    STATE["ports"] = ports
    STATE["ingress"] = metadata_ingress_entries(metadata)


async def refresh_presence():
    timeout = aiohttp.ClientTimeout(total=1.5)
    try:
        async with aiohttp.ClientSession(timeout=timeout, headers={"User-Agent": "HomeNetOps/1.0"}) as session:
            async with session.get(PRESENCE_URL, proxy=None) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
    except Exception as e:
        previous = STATE.get("presence", {}) if isinstance(STATE.get("presence"), dict) else {}
        STATE["presence"] = {
            **previous,
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "updated_at": time.time(),
        }
        return

    nested = data.get("state") if isinstance(data.get("state"), dict) else {}
    aps = nested.get("aps") if isinstance(nested.get("aps"), dict) else {}
    now = time.time()
    normalized_aps = {}
    for name, ap in aps.items():
        if not isinstance(ap, dict):
            continue
        updated_at = float(ap.get("updated_at") or 0)
        normalized_aps[name] = {
            "clients": ap.get("clients") or [],
            "remote_addr": ap.get("remote_addr") or "",
            "updated_at": updated_at,
            "age_seconds": round(max(0, now - updated_at)) if updated_at else None,
        }

    updated_at = float(nested.get("updated_at") or data.get("updated_at") or 0)
    STATE["presence"] = {
        "ok": bool(data.get("ok")),
        "seen_all": bool(data.get("seen_all")),
        "expected_aps": data.get("expected_aps") or [],
        "fresh_aps": data.get("fresh_aps") or [],
        "merged_clients": data.get("merged_clients") or [],
        "aps": normalized_aps,
        "last_ha_push": nested.get("last_ha_push") or {},
        "updated_at": updated_at,
        "age_seconds": round(max(0, now - updated_at)) if updated_at else None,
    }


def refresh_remote_access():
    previous = STATE.get("remote_access", {}) if isinstance(STATE.get("remote_access"), dict) else {}
    try:
        with open(WIREGUARD_STATUS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except OSError as e:
        STATE["remote_access"] = {
            **previous,
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "updated_at": time.time(),
        }
        return
    except json.JSONDecodeError as e:
        STATE["remote_access"] = {
            **previous,
            "ok": False,
            "error": f"JSONDecodeError: {e}",
            "updated_at": time.time(),
        }
        return

    now = time.time()
    clients = []
    for row in data.get("clients") or []:
        if not isinstance(row, dict):
            continue
        last_seen_at = row.get("last_seen_at")
        clients.append({
            "name": row.get("name") or "unknown",
            "enabled": bool(row.get("enabled", True)),
            "ipv4_address": row.get("ipv4_address") or "",
            "ipv6_address": row.get("ipv6_address") or "",
            "endpoint_scope": row.get("endpoint_scope") or "none",
            "has_endpoint": bool(row.get("has_endpoint")),
            "latest_handshake": row.get("latest_handshake") or "never",
            "latest_handshake_seconds": row.get("latest_handshake_seconds"),
            "last_seen_at": last_seen_at,
            "age_seconds": round(max(0, now - float(last_seen_at))) if last_seen_at else None,
            "status": row.get("status") or "idle",
            "transfer": row.get("transfer") or "",
        })
    STATE["remote_access"] = {
        "ok": bool(data.get("ok")),
        "clients": clients,
        "updated_at": float(data.get("updated_at") or 0),
        "active_after_seconds": data.get("active_after_seconds"),
        "stale_after_seconds": data.get("stale_after_seconds"),
        "error": data.get("error") or "",
    }


async def refresh_ops_network():
    remote = r"""
echo __NETWORK__
uci show network.ops 2>/dev/null
echo __DHCP__
uci show dhcp.ops 2>/dev/null
echo __WIRELESS__
for s in $(uci show wireless 2>/dev/null | sed -n "s/^\(wireless\.[^.]*\)\.network='ops'$/\1/p"); do
  uci show "$s" 2>/dev/null | grep -v "\.key="
done
echo __FIREWALL__
iptables -S 2>/dev/null | grep -E 'zone_ops|Allow-Control|wlan0-3' || true
echo __MANGLE__
iptables -t mangle -S PREROUTING 2>/dev/null || true
echo __LEASES__
cat /tmp/dhcp.leases 2>/dev/null | awk '$3 ~ /^192\.168\.40\./ {print $2, $3, $4}'
echo __ASSOC__
iwinfo wlan0-3 assoclist 2>/dev/null | grep -E '^[0-9A-Fa-f:]{17}' || true
"""
    previous = STATE.get("ops_network", {}) if isinstance(STATE.get("ops_network"), dict) else {}
    code, out, err = await run_cmd(ssh_cmd(remote), timeout=6)
    if code != 0:
        STATE["ops_network"] = {
            **previous,
            "ok": False,
            "error": err.strip() or f"exit {code}",
            "updated_at": time.time(),
        }
        return

    sections = {}
    current = ""
    for line in out.splitlines():
        if line.startswith("__") and line.endswith("__"):
            current = line.strip("_").lower()
            sections[current] = []
            continue
        if current:
            sections.setdefault(current, []).append(line)

    network = parse_uci_lines("\n".join(sections.get("network", [])))
    dhcp = parse_uci_lines("\n".join(sections.get("dhcp", [])))
    wireless = parse_uci_lines("\n".join(sections.get("wireless", [])))
    firewall_text = "\n".join(sections.get("firewall", []))
    mangle_text = "\n".join(sections.get("mangle", []))
    lease_rows = []
    for line in sections.get("leases", []):
        parts = line.split()
        if len(parts) >= 3:
            lease_rows.append({"mac": parts[0].lower(), "ip": parts[1], "name": parts[2] if parts[2] != "*" else "unknown"})

    ssid = next((v for k, v in wireless.items() if k.endswith(".ssid")), "Maintenance Wi-Fi")
    iface = next((k.split(".")[1] for k, v in wireless.items() if k.endswith(".ssid") and v == ssid), "")
    network_name = next((v for k, v in wireless.items() if k.endswith(".network")), "")
    disabled = next((v for k, v in wireless.items() if k.endswith(".disabled")), "0")
    isolated = next((v for k, v in wireless.items() if k.endswith(".isolate")), "0")
    ipaddr = network.get("network.ops.ipaddr", "")
    netmask = network.get("network.ops.netmask", "")
    dhcp_start = dhcp.get("dhcp.ops.start", "")
    dhcp_limit = dhcp.get("dhcp.ops.limit", "")
    dhcp_options = dhcp.get("dhcp.ops.dhcp_option", "")
    dns_servers = parse_dhcp_dns(dhcp_options)
    dhcp_range = f"{dhcp_start}-{int(dhcp_start) + int(dhcp_limit) - 1}" if dhcp_start.isdigit() and dhcp_limit.isdigit() else ""

    server_rule = f"{HOMENET_SERVER_IP}/32"
    allow_pi_ssh = server_rule in firewall_text and "--dport 22" in firewall_text
    allow_pi_homenet = server_rule in firewall_text and "--dport 9999" in firewall_text
    allow_wan = "Zone ops to wan forwarding policy" in firewall_text and "zone_wan_dest_ACCEPT" in firewall_text
    input_reject = "zone_ops_src_REJECT" in firewall_text
    proxy_bypassed = "-i br-lan -j MIHOMO_POLICY" in mangle_text and "wlan0-3" not in mangle_text and "br-ops" not in mangle_text

    checks = [
        ok_check("Maintenance SSID", bool(ssid and disabled != "1" and network_name == "ops"), f"{ssid} -> {network_name or 'unknown'}"),
        ok_check("Maintenance DHCP", bool(ipaddr == "192.168.40.1" and dhcp_range), f"{ipaddr}/{netmask} · {dhcp_range or 'range unknown'}"),
        ok_check("公共 DNS", bool(dns_servers), dns_servers or "未从 DHCP option 读取到 DNS", warn=True),
        ok_check("到 Pi SSH", allow_pi_ssh, f"Maintenance 客户端可访问 {HOMENET_SERVER_IP}:22"),
        ok_check("到 HomeNet", allow_pi_homenet, f"Maintenance 客户端可访问 {HOMENET_SERVER_IP}:9999"),
        ok_check("到 WAN", allow_wan, "Maintenance 客户端可直接出公网"),
        ok_check("隔离入口", bool(isolated == "1" and input_reject), "禁止访问路由器管理面，只保留 DHCP"),
        ok_check("绕开透明代理", proxy_bypassed, "Maintenance network 不进入 OpenWrt MIHOMO_POLICY"),
    ]

    STATE["ops_network"] = {
        "ok": all(item["status"] == "ok" for item in checks),
        "ssid": ssid,
        "iface": iface,
        "network": network_name,
        "gateway": ipaddr,
        "netmask": netmask,
        "dhcp_range": dhcp_range,
        "dns": dns_servers,
        "proxy_bypassed": proxy_bypassed,
        "clients": lease_rows,
        "checks": checks,
        "updated_at": time.time(),
    }


async def refresh_wifi_diagnostics():
    remote = f"""
echo __RADIO1__
wifi status radio1 2>/dev/null
echo __GUARD__
cat /tmp/wifi-radio1-guard.last 2>/dev/null || true
echo __BACKHAUL_ASSOC__
iwinfo wlan1-2 assoclist 2>/dev/null | sed -n '1,14p'
echo __ROOM_PING__
ping -c 1 -W 1 {ROOM_AP_IP} >/dev/null 2>&1 && echo up || echo down
"""
    previous = STATE.get("wifi_diagnostics", {}) if isinstance(STATE.get("wifi_diagnostics"), dict) else {}
    code, out, err = await run_cmd(ssh_cmd(remote), timeout=6)
    if code != 0:
        STATE["wifi_diagnostics"] = {
            **previous,
            "ok": False,
            "error": err.strip() or f"exit {code}",
            "updated_at": time.time(),
        }
        return

    sections = {}
    current = ""
    for line in out.splitlines():
        if line.startswith("__") and line.endswith("__"):
            current = line.strip("_").lower()
            sections[current] = []
            continue
        if current:
            sections.setdefault(current, []).append(line)

    radio_text = "\n".join(sections.get("radio1", [])).strip()
    guard_text = "\n".join(sections.get("guard", [])).strip()
    assoc_text = "\n".join(sections.get("backhaul_assoc", [])).strip()
    room_ping = "\n".join(sections.get("room_ping", [])).strip()

    radio = {}
    try:
        parsed = json.loads(radio_text) if radio_text else {}
        radio = parsed.get("radio1") if isinstance(parsed.get("radio1"), dict) else {}
    except json.JSONDecodeError:
        radio = {}

    config = radio.get("config") if isinstance(radio.get("config"), dict) else {}
    iface_rows = radio.get("interfaces") if isinstance(radio.get("interfaces"), list) else []
    ssids = []
    for row in iface_rows:
        if not isinstance(row, dict):
            continue
        cfg = row.get("config") if isinstance(row.get("config"), dict) else {}
        ssid = str(cfg.get("ssid") or "")
        if ssid:
            ssids.append(ssid)

    instance_wifi = STATE.get("instance", {}).get("wifi", {}) if isinstance(STATE.get("instance"), dict) else {}
    main_wifi = instance_wifi.get("main", {}) if isinstance(instance_wifi.get("main"), dict) else {}
    relay_wifi = instance_wifi.get("relay_5g", {}) if isinstance(instance_wifi.get("relay_5g"), dict) else {}
    main_ssid = str(main_wifi.get("ssid") or "Main Wi-Fi")
    backhaul_ssid = str(relay_wifi.get("ssid") or "Room backhaul")

    radio_up = bool(radio.get("up"))
    retry_failed = bool(radio.get("retry_setup_failed"))
    disabled = bool(config.get("disabled"))
    has_main = main_ssid in ssids
    has_backhaul = backhaul_ssid in ssids
    assoc_lines = [line for line in assoc_text.splitlines() if assoc_mac_re.match(line.strip().split()[0] if line.strip().split() else "")]
    if not assoc_lines:
        assoc_lines = [line for line in assoc_text.splitlines() if assoc_mac_re.search(line)]
    room_up = room_ping == "up"

    checks = [
        ok_check("主路由 5G radio1", radio_up and not retry_failed and not disabled, f"up={radio_up} retry_setup_failed={retry_failed} disabled={disabled}"),
        ok_check("主 Wi-Fi SSID", has_main, f"{main_ssid} 5G AP 已在 radio1 上广播" if has_main else f"radio1 SSID: {', '.join(ssids) or 'none'}"),
        ok_check("卧室回程 SSID", has_backhaul, f"{backhaul_ssid} 已在 radio1 上广播" if has_backhaul else f"radio1 SSID: {', '.join(ssids) or 'none'}"),
        ok_check("卧室 WRT 可达", room_up, f"{ROOM_AP_IP} ping up" if room_up else f"{ROOM_AP_IP} ping down"),
        ok_check("回程关联", bool(assoc_lines), f"{len(assoc_lines)} station(s) on wlan1-2" if assoc_lines else (assoc_text or "wlan1-2 no assoc")),
        ok_check("5G 自愈守护", "ok" in guard_text.lower(), guard_text or "guard state missing", warn=True),
    ]

    STATE["wifi_diagnostics"] = {
        "ok": all(item["status"] == "ok" for item in checks[:4]) and checks[5]["status"] != "bad",
        "radio1": {
            "up": radio_up,
            "retry_setup_failed": retry_failed,
            "disabled": disabled,
            "ssids": ssids,
        },
        "room_reachable": room_up,
        "backhaul_assoc_count": len(assoc_lines),
        "backhaul_assoc_sample": assoc_text,
        "guard": guard_text,
        "checks": checks,
        "updated_at": time.time(),
    }


def incident_domain(domain_id: str, title: str, status: str, detail: str, evidence: str, next_action: str, commands: List[str] | None = None) -> Dict:
    return {
        "id": domain_id,
        "title": title,
        "status": status,
        "detail": detail,
        "evidence": evidence,
        "next_action": next_action,
        "commands": commands or [],
    }


def incident_domain_by_id(domains: List[Dict]) -> Dict[str, Dict]:
    return {str(domain.get("id") or ""): domain for domain in domains if isinstance(domain, dict)}


def incident_status(domains: List[Dict], *domain_ids: str) -> str:
    by_id = incident_domain_by_id(domains)
    return worst_status([str((by_id.get(domain_id) or {}).get("status") or "unknown") for domain_id in domain_ids])


def incident_decision_flow(domains: List[Dict]) -> List[Dict]:
    by_id = incident_domain_by_id(domains)

    def commands(domain_id: str) -> List[str]:
        return [str(command) for command in (by_id.get(domain_id) or {}).get("commands", [])[:3]]

    return [
        {
            "id": "keep-maintenance",
            "order": 1,
            "domain": "rescue-path",
            "status": incident_status(domains, "rescue-path"),
            "question": "还能不能通过低依赖通道进 Pi/OpenWrt？",
            "why_first": "没有维护通道就不要扩大改动；先保证还能观察和回滚。",
            "if_bad": [
                "用 Maintenance Wi-Fi 或直连 IP 访问 OpenWrt/Pi。",
                "只检查 DHCP、firewall、SSID 和到 Pi/OpenWrt 的路径。",
            ],
            "entries": [f"http://{HOMENET_SERVER_IP}:9999/", "ssh pi", "ssh wrt"],
        },
        {
            "id": "prove-gateway",
            "order": 2,
            "domain": "gateway-wan",
            "status": incident_status(domains, "gateway-wan"),
            "question": "主路由、LAN、WAN 是不是基础正常？",
            "why_first": "Gateway/WAN 不正常时，DNS、Proxy、Cloudflare、Kuma 的异常都可能是下游假象。",
            "if_bad": [
                "先看 OpenWrt WAN、接口状态、DHCP 和防火墙。",
                "不要先重启 Pi 服务或改 Mihomo/AdGuard。",
            ],
            "entries": commands("gateway-wan") or [f"http://{OPENWRT_HOST}/cgi-bin/luci", "ssh wrt"],
        },
        {
            "id": "prove-wifi",
            "order": 3,
            "domain": "main-wifi-5g",
            "status": incident_status(domains, "main-wifi-5g", "room-ap"),
            "question": "问题是不是 Wi-Fi radio/SSID/卧室回程？",
            "why_first": "断电后来电 5G 不起、卧室覆盖不稳，通常要先证明 radio 和 client association。",
            "if_bad": [
                "只检查 OpenWrt wireless status、radio1 和 Room AP upstream。",
                "客户端单点异常时先看该设备 SSID-specific MAC 和 DHCP lease。",
            ],
            "entries": list(dict.fromkeys(commands("main-wifi-5g") + commands("room-ap")))[:4],
        },
        {
            "id": "prove-dns-proxy",
            "order": 4,
            "domain": "dns-proxy",
            "status": incident_status(domains, "dns-proxy"),
            "question": "是 DNS 解析错，还是 Proxy 路由/节点慢？",
            "why_first": "国内慢、国外慢、AI 节点走错组，需要先拆开 DNS answer、rule match、proxy group health。",
            "if_bad": [
                "先看 AdGuard/router DNS，再看 Mihomo rule/provider/group。",
                "如果只有某个客户端异常，先排客户端代理模式和系统 DNS。",
            ],
            "entries": commands("dns-proxy") or [f"http://{HOMENET_SERVER_IP}:9090/ui/#/proxies"],
        },
        {
            "id": "prove-server",
            "order": 5,
            "domain": "server-runtime",
            "status": incident_status(domains, "server-runtime"),
            "question": "是不是 Pi 上一组服务一起异常？",
            "why_first": "HomeNet/Kuma/Mihomo/AdGuard/HA 一起异常时，先当作 server runtime 事件处理。",
            "if_bad": [
                "先查 Docker/systemd、磁盘、内存和端口监听。",
                "LAN 本地服务没好之前，不诊断 Cloudflare 外部入口。",
            ],
            "entries": commands("server-runtime") or ["ssh pi", "docker ps", "ss -ltn"],
        },
        {
            "id": "prove-remote",
            "order": 6,
            "domain": "remote-access",
            "status": incident_status(domains, "remote-access"),
            "question": "外部入口坏，还是它背后的 LAN 服务坏？",
            "why_first": "外部域名失败必须和对应 LAN target 配对看，否则容易误改 Cloudflare。",
            "if_bad": [
                "LAN target 正常才看 Cloudflare Tunnel/Access/Caddy/DDNS/WireGuard。",
                "LAN target 也坏就回到 Pi runtime 或 Gateway/WAN。",
            ],
            "entries": [f"http://{HOMENET_SERVER_IP}:9999/", "https://external Ops URL/", *commands("remote-access")[:1]],
        },
    ]


def incident_recovery_matrix(domains: List[Dict]) -> List[Dict]:
    rows = [
        ("所有 Wi-Fi/有线都慢或无网", "gateway-wan", f"http://{OPENWRT_HOST}/cgi-bin/luci", "WAN interface, DHCP lease, DNS handed to client", "OpenWrt Gateway / ISP modem", "Mihomo provider, Cloudflare, HA, or Kuma"),
        ("断电后来电 5G/SSID 不出现", "main-wifi-5g", f"http://{OPENWRT_HOST}/cgi-bin/luci", "radio1 enabled, SSID broadcast, client association, system log", "OpenWrt wireless config", "DNS/proxy rules"),
        ("卧室慢、切 AP 不顺、Room AP 客户端异常", "room-ap", f"http://{ROOM_AP_IP}/ from main LAN; http://{ROOM_AP_LOCAL_IP}/ when connected under WRT Room", "Room AP upstream/backhaul, DHCP server disabled, client lease source", "Room AP LuCI/SSH + Gateway wireless", "global Wi-Fi redesign"),
        ("国内 App 开代理很慢，关代理正常", "dns-proxy", f"http://{HOMENET_SERVER_IP}:9090/ui/#/proxies", "rule match, DIRECT path, selected proxy group, DNS result type", "Mihomo rules + AdGuard/router DNS", "WAN reboot unless direct path also fails"),
        ("HomeNet/Kuma/HA/Mihomo/AdGuard 一起掉", "server-runtime", "ssh pi", "Docker ps, systemd units, listening ports, disk/memory", "Pi Docker/systemd", "Cloudflare Access settings"),
        ("外部域名打不开，但 LAN 可能正常", "remote-access", f"http://{HOMENET_SERVER_IP}:9999/", "Cloudflare Tunnel/Access, Caddy/DDNS, WireGuard handshake", "Cloudflare / cloudflared / Caddy / WireGuard", "service restart before local target is checked"),
        ("单个设备 IP/名字不对，尤其 Apple 或 IoT", "client-device", f"http://{OPENWRT_HOST}/cgi-bin/luci", "SSID-specific MAC, static lease, hostname source, device power state", "OpenWrt DHCP/static lease + device native settings", "whole-network changes"),
    ]
    return [
        {
            "symptom": symptom,
            "start_domain": domain_id,
            "status": incident_status(domains, domain_id),
            "first_probe": first_probe,
            "then_probe": then_probe,
            "likely_owner": owner,
            "do_not_start_with": avoid,
        }
        for symptom, domain_id, first_probe, then_probe, owner, avoid in rows
    ]


def update_incident_summary():
    services = STATE.get("home_services", [])
    checks = STATE.get("health", {}).get("checks", [])
    wifi = STATE.get("wifi_diagnostics", {}) if isinstance(STATE.get("wifi_diagnostics"), dict) else {}
    ops = STATE.get("ops_network", {}) if isinstance(STATE.get("ops_network"), dict) else {}
    remote = STATE.get("remote_access", {}) if isinstance(STATE.get("remote_access"), dict) else {}

    gateway_status = worst_status([service_status("openwrt-luci"), service_status("openwrt-ssh")])
    if status_is_ok(service_status("openwrt-luci")) or status_is_ok(service_status("openwrt-ssh")):
        gateway_status = "ok"
    wan_if = STATE.get("wan", {}).get("if") or WAN_IF

    wifi_bad = [item for item in wifi.get("checks", []) if item.get("status") == "bad"]
    wifi_warn = [item for item in wifi.get("checks", []) if item.get("status") == "warn"]
    wifi_status = "bad" if wifi_bad else ("warn" if wifi_warn else ("ok" if wifi.get("ok") else "unknown"))

    room_status = worst_status([service_status("wrt-room-luci"), service_status("wrt-room-ssh")])
    if wifi.get("room_reachable") and room_status != "bad":
        room_status = "ok"
    elif not wifi.get("room_reachable"):
        room_status = "bad"

    dns_related = [item for item in checks if "DNS" in f"{item.get('title')} {item.get('detail')}" or "域名" in str(item.get("title") or "")]
    dns_status = worst_status([str(item.get("status") or "unknown") for item in dns_related] + [service_status("adguard"), service_status("mihomo")])
    if all(status_is_ok(service_status(key)) for key in ("adguard", "mihomo")) and not any(item.get("status") == "bad" for item in dns_related):
        dns_status = "ok" if not any(item.get("status") == "warn" for item in dns_related) else "warn"

    pi_keys = ["homenet-ops", "adguard", "mihomo", "uptime-kuma", "home-assistant", "cloudflared", "wireguard"]
    pi_bad = [service_by_key(key) for key in pi_keys if service_status(key) == "bad"]
    pi_warn = [service_by_key(key) for key in pi_keys if service_status(key) == "warn"]
    pi_status = "bad" if pi_bad else ("warn" if pi_warn else "ok")

    remote_status = "ok" if remote.get("ok") or status_is_ok(service_status("cloudflared")) else "warn"
    rescue_status = "ok" if ops.get("ok") else "warn"

    domains = [
        incident_domain(
            "gateway-wan",
            "主路由 / WAN",
            gateway_status,
            "所有 LAN、Wi-Fi、透明代理入口都先经过 OpenWrt Gateway。",
            f"LuCI={service_status('openwrt-luci')} SSH={service_status('openwrt-ssh')} WAN_IF={wan_if}",
            "如果这里异常，先用 Maintenance Wi-Fi 或有线进路由，再确认拨号、DHCP 和防火墙。",
            ["ssh wrt", f"ifstatus wan", f"cat /sys/class/net/{wan_if}/operstate"],
        ),
        incident_domain(
            "main-wifi-5g",
            "主 Wi-Fi 5G / 回程 radio1",
            wifi_status,
            "断电来电后最容易出问题的是 radio1 没起来，Main Wi-Fi 5G 和 Room backhaul 会同时受影响。",
            " / ".join(f"{item.get('title')}={item.get('status')}" for item in wifi.get("checks", [])[:4]) or "等待 Wi-Fi 采样",
            "如果 radio1 failed，执行 guard 或只重启 radio1，不要大改网络配置。",
            ["/root/wifi-radio1-guard.sh", "wifi down radio1; sleep 2; wifi up radio1", "wifi status radio1"],
        ),
        incident_domain(
            "room-ap",
            "卧室 WRT / 房间覆盖",
            room_status,
            "卧室 WRT 通过 Room backhaul 回连主路由，再给卧室设备提供覆盖。",
            f"ping .2={'up' if wifi.get('room_reachable') else 'down'} backhaul_assoc={wifi.get('backhaul_assoc_count', 0)} LuCI={service_status('wrt-room-luci')}",
            f"如果主 5G 正常但 {ROOM_AP_IP} 不通，再查 WRT Room 的电源、位置和无线回程；手机连在 WRT Room 下时用 {ROOM_AP_LOCAL_IP} 看房间侧后台。",
            [f"ping {ROOM_AP_IP}", "ssh wrt-room", f"open http://{ROOM_AP_LOCAL_IP}/ from a WRT Room client", "iwinfo wlan1-2 assoclist"],
        ),
        incident_domain(
            "dns-proxy",
            "DNS / Mihomo",
            dns_status,
            "网页能不能打开、国内软件慢不慢、AI 节点走哪组，主要看 AdGuard + Mihomo。",
            f"AdGuard={service_status('adguard')} Mihomo={service_status('mihomo')} Health={len([c for c in dns_related if c.get('status') != 'ok'])} issue(s)",
            "如果国内外都慢，先看 DNS 是否返回 fake-ip 错位，再看 Mihomo 路由组和透明代理。",
            ["curl http://127.0.0.1:9090/version", "nslookup github.com 127.0.0.1", "nslookup aweme.snssdk.com 127.0.0.1"],
        ),
        incident_domain(
            "server-runtime",
            "Pi 服务",
            pi_status,
            "HomeNet、HA、Kuma、AdGuard、Mihomo、WireGuard、cloudflared 都在 Pi 上，Pi 异常会让很多入口一起掉。",
            f"{len(pi_bad)} bad / {len(pi_warn)} warn in core Pi services",
            "如果多个 Pi 服务同时异常，先查 Docker/systemd 和 Pi 网络，不要逐个服务乱改。",
            ["docker ps", "ss -ltn", "systemctl --failed"],
        ),
        incident_domain(
            "remote-access",
            "外部回家入口",
            remote_status,
            "外部入口分为 Cloudflare HTTPS、IPv6 direct 和 WireGuard；它们的职责不同。",
            f"WireGuard={'ok' if remote.get('ok') else 'check'} cloudflared={service_status('cloudflared')} Kuma={service_status('uptime-kuma')}",
            "外网不能回家时，分开看 Cloudflare Access、Tunnel、WireGuard handshake 和 IPv6。",
            ["docker logs cloudflared --tail 80", "docker logs wg-easy --tail 80"],
        ),
        incident_domain(
            "rescue-path",
            "检修通道",
            rescue_status,
            "Maintenance Wi-Fi 应该绕开透明代理和家庭 DNS，保留直出公网、Pi SSH、HomeNet 访问。",
            f"Maintenance Wi-Fi={'ok' if ops.get('ok') else 'check'} clients={len(ops.get('clients') or [])}",
            "主网络出问题时，用设备连 Maintenance Wi-Fi，再在设备上单独开代理访问 Codex，同时让 Codex SSH 到 Pi。",
            ["ssh pi", f"open http://{HOMENET_SERVER_IP}:9999/"],
        ),
        incident_domain(
            "client-device",
            "客户端 / 设备身份",
            "warn" if any(service.get("status") == "unknown" for service in services[:1]) else "ok",
            "单个设备异常时，优先看 DHCP lease、SSID-specific MAC、hostname 和设备自身状态。",
            f"active_clients={len(STATE.get('devices') or [])} dhcp_cache={len(mac_map)}",
            "不要因为一个设备的私有 MAC 或租约变化去改全网；先确认它当前连接的 SSID 和 MAC。",
            ["cat /tmp/dhcp.leases", "ip neigh show"],
        ),
    ]

    bad = [item for item in domains if item["status"] in {"bad", "down"}]
    warn = [item for item in domains if item["status"] == "warn"]
    if bad:
        headline = f"先处理：{bad[0]['title']}"
        ok = False
        severity = "bad"
    elif warn:
        headline = f"需要确认：{warn[0]['title']}"
        ok = False
        severity = "warn"
    else:
        headline = "关键链路正常"
        ok = True
        severity = "ok"

    STATE["incident"] = {
        "ok": ok,
        "severity": severity,
        "headline": headline,
        "summary": "按故障影响顺序检查：主路由/WAN -> 5G radio1 -> 卧室 WRT -> DNS/Proxy -> Pi 服务 -> 外部入口 -> 检修通道。",
        "domains": domains,
        "decision_flow": incident_decision_flow(domains),
        "recovery_matrix": incident_recovery_matrix(domains),
        "runbook": [
            "先看主路由和 WAN 是否可达；如果路由器不通，其他状态都不可信。",
            "来电后重点看 radio1：Main Wi-Fi 5G 和 Room backhaul 都依赖它。",
            f"radio1 正常后再看 {ROOM_AP_IP} 和回程关联，判断卧室覆盖是否恢复。",
            "家里能连 Wi-Fi 但网页慢或打不开时，再看 AdGuard/Mihomo/DNS 健康检查。",
            "多个入口同时坏时，优先查 Pi 的 Docker、systemd 和网络。",
            "需要远程检修时，连 Maintenance Wi-Fi，设备自己开代理，保持到 Pi 的 SSH/HomeNet 通路。",
        ],
        "updated_at": time.time(),
    }


def update_insights_and_history():
    now = time.time()
    wan_down = float(STATE.get("wan", {}).get("down_mbps") or 0)
    wan_up = float(STATE.get("wan", {}).get("up_mbps") or 0)
    mh_down = float(STATE.get("mihomo", {}).get("down_mbps") or 0)
    mh_up = float(STATE.get("mihomo", {}).get("up_mbps") or 0)
    devices = STATE.get("devices", [])
    routes = STATE.get("route_summary", [])
    dns_devices = STATE.get("dns_top_devices", [])

    top_device = max(devices, key=lambda d: (d.get("up_mbps", 0) + d.get("down_mbps", 0)), default=None)
    top_route = max(routes, key=lambda r: (r.get("up_mbps", 0) + r.get("down_mbps", 0)), default=None)
    top_dns = dns_devices[0] if dns_devices else None
    bypass_down = max(wan_down - mh_down, 0)
    bypass_ratio = bypass_down / wan_down if wan_down > 0.01 else 0

    insights = []
    if top_device:
        total = top_device.get("up_mbps", 0) + top_device.get("down_mbps", 0)
        insights.append({
            "level": "info",
            "title": "最活跃设备",
            "text": f"{top_device.get('name') or top_device.get('ip') or top_device.get('mac')} 当前合计 {total:.2f} Mbps",
        })
    if top_route:
        total = top_route.get("up_mbps", 0) + top_route.get("down_mbps", 0)
        insights.append({
            "level": "info",
            "title": "主要 Mihomo 出口",
            "text": f"{top_route.get('chain') or 'unknown'}，{total:.2f} Mbps，{top_route.get('connections', 0)} 个连接",
        })
    if top_dns:
        insights.append({
            "level": "info",
            "title": "DNS 最活跃",
            "text": f"{top_dns.get('device')} 最近 5 分钟 {top_dns.get('count', 0)} 次查询",
        })
    if bypass_ratio >= 0.5 and bypass_down >= 1:
        insights.append({
            "level": "warn",
            "title": "直连流量占比高",
            "text": f"WAN 下行约 {wan_down:.2f} Mbps，Mihomo 下行约 {mh_down:.2f} Mbps，可能主要是国内直连或旁路流量",
        })
    if any(d.get("name") == "h3c-rt3000-bridge" for d in devices + dns_devices):
        insights.append({
            "level": "info",
            "title": "H3C 桥接视角",
            "text": "H3C 后面的 IPv6 隐私地址可能只能归到桥接 MAC；IPv4 有 DHCP 租约时会优先按真实设备归属",
        })
    bad_health = [c for c in STATE.get("health", {}).get("checks", []) if c.get("status") in ("bad", "warn")]
    if bad_health:
        top = bad_health[0]
        insights.append({
            "level": "warn" if top.get("status") == "warn" else "bad",
            "title": f"健康检查：{top.get('title')}",
            "text": top.get("detail") or "只读健康检查发现异常",
        })
    bad_services = [s for s in STATE.get("home_services", []) if s.get("status") == "bad"]
    if bad_services:
        top = bad_services[0]
        insights.append({
            "level": "bad",
            "title": f"服务探针：{top.get('name')}",
            "text": top.get("detail") or "本机服务探针异常",
        })

    STATE["insights"] = insights[:8]

    history_samples.append({
        "time": now,
        "wan_down": wan_down,
        "wan_up": wan_up,
        "mihomo_down": mh_down,
        "mihomo_up": mh_up,
        "device_count": len(devices),
        "dns_count_5m": sum(int(d.get("count", 0)) for d in dns_devices),
    })
    cutoff = now - 600
    while history_samples and history_samples[0]["time"] < cutoff:
        history_samples.pop(0)
    STATE["history"] = history_samples[-600:]


async def sampler_loop():
    await refresh_dhcp_map()
    last_map = 0.0
    last_service_probe = 0.0
    last_heavy_probe = 0.0
    while True:
        start = time.time()
        STATE["errors"] = []
        if start - last_map > DHCP_INTERVAL:
            await refresh_dhcp_map()
            last_map = start
        await read_wan_counters()
        await read_device_counters()
        await read_dns_queries()
        try:
            await read_mihomo()
        except Exception as e:
            add_error(f"mihomo sampler failed: {e}")
        if start - last_service_probe > SERVICE_PROBE_INTERVAL:
            try:
                await refresh_home_services()
            except Exception as e:
                add_error(f"home service probe failed: {e}")
            try:
                await refresh_presence()
            except Exception as e:
                add_error(f"presence probe failed: {e}")
            try:
                refresh_remote_access()
            except Exception as e:
                add_error(f"remote access probe failed: {e}")
            last_service_probe = start
        if start - last_heavy_probe > HEAVY_PROBE_INTERVAL:
            try:
                await refresh_ops_network()
            except Exception as e:
                add_error(f"ops network probe failed: {e}")
            try:
                await refresh_wifi_diagnostics()
            except Exception as e:
                add_error(f"wifi diagnostics failed: {e}")
            last_heavy_probe = start
        update_incident_summary()
        update_insights_and_history()
        STATE["ok"] = True
        STATE["updated_at"] = time.time()
        await asyncio.sleep(max(REFRESH - (time.time() - start), 0.05))


async def index(request):
    return web.FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


async def api_state(request):
    state = {**STATE, "errors": recent_errors()}
    return web.json_response(state)


async def api_health(request):
    await ensure_health_checks()
    return web.json_response({
        "updated_at": STATE.get("health", {}).get("updated_at", 0),
        "checks": STATE.get("health", {}).get("checks", []),
        "errors": recent_errors(),
        "state_updated_at": STATE.get("updated_at", 0),
    })


async def api_health_mac_studio(request):
    checks = []
    for path in MAC_STUDIO_PATHS:
        ip = path["ip"]
        code, out, err = await run_cmd(ssh_cmd(f"ping -c 1 -W 2 {ip} >/dev/null 2>&1 && echo up || echo down"), timeout=4)
        up = code == 0 and out.strip() == "up"
        checks.append({
            "name": path["name"],
            "ip": ip,
            "status": "up" if up else "down",
            "detail": "" if up else (err.strip() or "ping failed"),
        })

    online = any(item["status"] == "up" for item in checks)
    status = 200 if online else 503
    active = next((item for item in checks if item["status"] == "up"), None)
    body = {
        "status": "ok" if online else "down",
        "name": "Mac Studio",
        "active_path": active["name"] if active else "",
        "checks": checks,
        "updated_at": time.time(),
    }
    return web.json_response(body, status=status)


async def api_routing_rules(request):
    data = load_routing_store()
    entries = active_routing_entries(data)
    return web.json_response({
        "ok": True,
        "policies": [{"id": key, "label": meta["label"]} for key, meta in ROUTING_POLICIES.items()],
        "durations": list(ROUTING_DURATIONS.keys()),
        "entries": entries,
        "permanent_candidates": routing_permanent_candidates(data),
        "updated_at": time.time(),
    })


async def api_routing_rules_add(request):
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"ok": False, "error": "invalid JSON"}, status=400)

    try:
        target = normalize_routing_target(str(payload.get("target") or ""))
    except ValueError as e:
        return web.json_response({"ok": False, "error": str(e)}, status=400)

    policy = str(payload.get("policy") or "PROXY").upper()
    if policy not in ROUTING_POLICIES:
        return web.json_response({"ok": False, "error": f"unsupported policy {policy}"}, status=400)

    wants_permanent = bool(payload.get("permanent"))
    scope = "temporary"
    duration = str(payload.get("duration") or "1h")
    if not wants_permanent and duration not in ROUTING_DURATIONS:
        return web.json_response({"ok": False, "error": f"unsupported duration {duration}"}, status=400)

    now = time.time()
    expires_at = None
    if not wants_permanent:
        seconds = ROUTING_DURATIONS.get(duration)
        expires_at = None if seconds is None else now + seconds

    item = {
        "id": f"{scope}:{policy}:{target['value']}",
        "scope": scope,
        "policy": policy,
        "kind": target["kind"],
        "value": target["value"],
        "rule": target["rule"],
        "duration": duration,
        "created_at": now,
        "expires_at": expires_at,
    }

    if wants_permanent:
        candidate = save_routing_permanent_candidate(item)
        return web.json_response({
            "ok": True,
            "detail": "created permanent candidate only; runtime routing unchanged",
            "entries": active_routing_entries(),
            "permanent_candidates": routing_permanent_candidates(),
            "candidate": candidate,
        })

    data = load_routing_store()
    existing_entries = active_routing_entries(data)
    removed_entries = [
        item for item in existing_entries
        if item.get("value") == target["value"] and item.get("scope") == scope
    ]
    entries = [item for item in existing_entries if item not in removed_entries]
    entries.append(item)
    save_routing_store({"entries": entries})
    ok, detail = await apply_routing_rules()
    return web.json_response({"ok": ok, "detail": detail, "entries": active_routing_entries(), "permanent_candidates": routing_permanent_candidates()}, status=200 if ok else 502)


async def api_routing_rules_delete(request):
    rule_id = request.match_info.get("rule_id", "")
    data = load_routing_store()
    current_entries = active_routing_entries(data)
    entries = [item for item in current_entries if item.get("id") != rule_id]
    save_routing_store({**data, "entries": entries})
    ok, detail = await apply_routing_rules()
    return web.json_response({"ok": ok, "detail": detail, "entries": active_routing_entries(), "permanent_candidates": routing_permanent_candidates()}, status=200 if ok else 502)


async def api_routing_rules_promote(request):
    rule_id = request.match_info.get("rule_id", "")
    data = load_routing_store()
    source = None
    for item in active_routing_entries(data):
        if item.get("id") == rule_id:
            source = item
            break
    if not source:
        return web.json_response({"ok": False, "error": "rule not found"}, status=404)
    candidate = save_routing_permanent_candidate(source)
    return web.json_response({
        "ok": True,
        "detail": "created permanent candidate; temporary runtime rule unchanged",
        "entries": active_routing_entries(),
        "permanent_candidates": routing_permanent_candidates(),
        "candidate": candidate,
    })


async def api_routing_permanent_delete(request):
    candidate_id = request.match_info.get("candidate_id", "")
    data = load_routing_store()
    candidates = [
        item for item in routing_permanent_candidates(data)
        if item.get("id") != candidate_id
    ]
    save_routing_store({**data, "permanent_candidates": candidates})
    return web.json_response({
        "ok": True,
        "entries": active_routing_entries(),
        "permanent_candidates": routing_permanent_candidates(),
    })


async def events(request):
    resp = web.StreamResponse(status=200, reason='OK', headers={
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
    })
    await resp.prepare(request)
    try:
        while True:
            await resp.write(f"data: {json.dumps(STATE, ensure_ascii=False)}\n\n".encode())
            await asyncio.sleep(REFRESH)
    except (asyncio.CancelledError, ConnectionError, ConnectionResetError, BrokenPipeError, TimeoutError, RuntimeError):
        pass
    return resp


async def on_startup(app):
    app['tasks'] = [asyncio.create_task(sampler_loop())]


async def on_cleanup(app):
    for t in app.get('tasks', []):
        t.cancel()


@web.middleware
async def no_store_middleware(request, handler):
    response = await handler(request)
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


app = web.Application(middlewares=[no_store_middleware])
app.router.add_get('/', index)
app.router.add_get('/api/state', api_state)
app.router.add_get('/api/health', api_health)
app.router.add_get('/api/health/mac-studio', api_health_mac_studio)
app.router.add_get('/api/routing-rules', api_routing_rules)
app.router.add_post('/api/routing-rules', api_routing_rules_add)
app.router.add_delete('/api/routing-rules/{rule_id:.+}', api_routing_rules_delete)
app.router.add_post('/api/routing-rules/{rule_id:.+}/promote', api_routing_rules_promote)
app.router.add_delete('/api/routing-permanent/{candidate_id:.+}', api_routing_permanent_delete)
app.router.add_get('/events', events)
app.router.add_static('/assets/', os.path.join(os.path.dirname(__file__), "static", "assets"), name='assets')
app.on_startup.append(on_startup)
app.on_cleanup.append(on_cleanup)

if __name__ == '__main__':
    web.run_app(app, host='0.0.0.0', port=int(os.getenv('PORT', '9876')))
