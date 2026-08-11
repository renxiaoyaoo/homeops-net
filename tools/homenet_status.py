from __future__ import annotations

from typing import Any


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def classify_live_diagnostic_domains(area: str, message: str) -> list[str]:
    text = f"{area} {message}".lower()
    if "remote ingress" in text:
        return ["remote-access"]
    domains: set[str] = set()
    rules = [
        ("gateway-wan", ["openwrt ssh not reachable", "openwrt ssh", "wan", "pppoe", "gateway", "dhcp leases unavailable", "cannot query openwrt"]),
        ("wifi-radio", ["radio1", "5ghz", "5g", "wlan1", "wireless", "wi-fi", "wifi", "ssid", "weak 5ghz"]),
        ("room-ap", ["wrt-room", "room ap", "room-ap", "relay", "backhaul", "bedroom coverage"]),
        ("dns-proxy", ["dns", "adguard", "mihomo", "fake-ip", "tproxy", "mangle chain", "table 100", "fwmark", "github.com", "google.com", "baidu.com", "proxy path", "direct path"]),
        ("server-runtime", ["docker", "container", "systemd", "not active", "homenet api", "generated config", "not visible in docker ps"]),
        ("remote-access", ["remote ingress", "cloudflare", "access apps", "tunnel api", "wireguard", "wg-easy", "ddns", "ipv6 https"]),
        ("smart-home", ["apple home", "homekit", "home hub", "airplay", "_hap._tcp", "_airplay._tcp", "home assistant", "mqtt", "zigbee", "matter", "thread"]),
        ("rescue-path", ["maintenance", "rescue", "ops wifi", "ops network", "homenet api unavailable", "openwrt ssh not reachable"]),
        ("client-device", ["dhcp leases", "not seen in current dhcp leases", "expected", "current dhcp ip", "hostname", "device", "client", "mac"]),
    ]
    for domain, needles in rules:
        if any(needle in text for needle in needles):
            domains.add(domain)
    if "openwrt" in text and ("policy" in text or "route" in text or "dnsmasq" in text):
        domains.update({"gateway-wan", "dns-proxy"})
    if "not reachable via proxy path" in text:
        domains.add("dns-proxy")
    elif "not reachable via direct path" in text:
        domains.update({"gateway-wan", "dns-proxy"})
    if "homenet api unavailable" in text:
        domains.update({"server-runtime", "rescue-path"})
    if not domains:
        domains.add("server-runtime" if area == "live" else "gateway-wan")
    return sorted(domains)


def summarize_live_diagnostic_findings(findings: list[Any]) -> dict[str, Any]:
    classified: list[dict[str, Any]] = []
    domain_counts: dict[str, dict[str, int]] = {}
    for finding in findings:
        if getattr(finding, "level", None) not in {"FAIL", "WARN"}:
            continue
        area = str(getattr(finding, "area", ""))
        message = str(getattr(finding, "message", ""))
        domains = classify_live_diagnostic_domains(area, message)
        level = str(getattr(finding, "level", ""))
        level_key = "fail" if level == "FAIL" else "warn"
        row = {
            "level": level,
            "area": area,
            "message": message,
            "domains": domains,
        }
        classified.append(row)
        for domain in domains:
            counts = domain_counts.setdefault(domain, {"fail": 0, "warn": 0})
            counts[level_key] += 1
    return {
        "classified_findings": classified,
        "domain_counts": dict(sorted(domain_counts.items())),
    }


def build_diagnostic_surface(
    metadata: dict[str, Any],
    rescue: dict[str, Any],
    live_summary: dict[str, Any],
    *,
    live: bool,
) -> dict[str, Any]:
    services = [
        service
        for service in as_list(metadata.get("service_directory"))
        if isinstance(service, dict)
    ]
    services_by_id = {str(service.get("id") or ""): service for service in services}
    networks = metadata.get("networks", {}) if isinstance(metadata.get("networks"), dict) else {}
    wifi = metadata.get("wifi", {}) if isinstance(metadata.get("wifi"), dict) else {}
    runtime = metadata.get("runtime_targets", {}) if isinstance(metadata.get("runtime_targets"), dict) else {}
    maintenance = rescue.get("maintenance_network", {}) if isinstance(rescue.get("maintenance_network"), dict) else {}
    remote_entries = [entry for entry in as_list(metadata.get("remote_ingress")) if isinstance(entry, dict)]
    local_entries = [entry for entry in as_list(rescue.get("local_entries")) if isinstance(entry, dict)]
    local_by_id = {str(entry.get("id") or ""): entry for entry in local_entries}
    remote_by_service = {
        str(entry.get("service_id") or ""): entry
        for entry in remote_entries
        if entry.get("service_id")
    }
    top_findings = [finding for finding in as_list(live_summary.get("top_findings")) if isinstance(finding, dict)]
    classified_findings = [
        finding
        for finding in as_list(live_summary.get("classified_findings"))
        if isinstance(finding, dict)
    ] or [
        {**finding, "domains": classify_live_diagnostic_domains(str(finding.get("area") or ""), str(finding.get("message") or ""))}
        for finding in top_findings
    ]
    domain_counts = live_summary.get("domain_counts", {}) if isinstance(live_summary.get("domain_counts"), dict) else {}

    def service(service_id: str) -> dict[str, Any]:
        item = services_by_id.get(service_id) or {}
        return {
            "id": service_id,
            "name": item.get("name") or service_id,
            "host": item.get("host") or "",
            "local_url": item.get("local_url") or "",
            "remote_url": item.get("remote_url") or "",
            "runtime": item.get("runtime") or "",
            "owner": item.get("owner") or item.get("runtime") or "",
        }

    def first_entries(*ids: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for entry_id in ids:
            entry = local_by_id.get(entry_id)
            if entry:
                rows.append({
                    "id": entry_id,
                    "name": entry.get("name") or entry_id,
                    "target": entry.get("target") or entry.get("local_url") or entry.get("host") or "",
                    "dependency": entry.get("dependency") or "",
                })
                continue
            svc = service(entry_id)
            target = svc.get("local_url") or svc.get("host") or ""
            if target:
                rows.append({
                    "id": entry_id,
                    "name": svc.get("name") or entry_id,
                    "target": target,
                    "dependency": svc.get("runtime") or "",
                })
        return rows

    def remote_pair(service_id: str) -> dict[str, Any] | None:
        entry = remote_by_service.get(service_id)
        if entry:
            return {
                "id": entry.get("id") or "",
                "name": entry.get("name") or "",
                "href": entry.get("href") or "",
                "kind": entry.get("kind") or "",
                "target": entry.get("target") or "",
            }
        svc = services_by_id.get(service_id) or {}
        href = str(svc.get("remote_url") or "")
        if not href:
            return None
        return {
            "id": service_id,
            "name": svc.get("name") or service_id,
            "href": href,
            "kind": "service-remote-url",
            "target": service_id,
        }

    def domain_status(domain_id: str, keywords: list[str]) -> str:
        if not live_summary.get("checked"):
            return "unknown"
        counts = domain_counts.get(domain_id, {}) if isinstance(domain_counts.get(domain_id), dict) else {}
        if int(counts.get("fail") or 0):
            return "bad"
        if int(counts.get("warn") or 0):
            return "warn"
        if classified_findings:
            return "ok" if live else "unknown"
        matched = [
            finding
            for finding in classified_findings
            if domain_id in as_list(finding.get("domains"))
            or any(keyword in f"{finding.get('area', '')} {finding.get('message', '')}".lower() for keyword in keywords)
        ]
        if any(str(finding.get("level") or "").upper() == "FAIL" for finding in matched):
            return "bad"
        if matched:
            return "warn"
        if live:
            return "ok"
        return "unknown"

    def domain_live_evidence(domain_id: str) -> dict[str, Any]:
        counts = domain_counts.get(domain_id, {}) if isinstance(domain_counts.get(domain_id), dict) else {}
        related = [
            {
                "level": finding.get("level") or "",
                "area": finding.get("area") or "",
                "message": finding.get("message") or "",
            }
            for finding in classified_findings
            if domain_id in as_list(finding.get("domains"))
        ][:5]
        return {
            "checked": bool(live_summary.get("checked")),
            "failures": int(counts.get("fail") or 0),
            "warnings": int(counts.get("warn") or 0),
            "related_findings": related,
        }

    gateway = str(runtime.get("openwrt_gateway") or "")
    server = runtime.get("server", {}) if isinstance(runtime.get("server"), dict) else {}
    server_host = str(server.get("host") or "")
    room_ap = runtime.get("room_ap", {}) if isinstance(runtime.get("room_ap"), dict) else {}
    room_host = str(room_ap.get("host") or "")
    lan = networks.get("lan", {}) if isinstance(networks.get("lan"), dict) else {}
    ops = networks.get("ops", {}) if isinstance(networks.get("ops"), dict) else {}
    main_wifi = wifi.get("main", {}) if isinstance(wifi.get("main"), dict) else {}
    relay_wifi = wifi.get("relay_5g", {}) if isinstance(wifi.get("relay_5g"), dict) else {}
    maintenance_wifi = wifi.get("ops", {}) if isinstance(wifi.get("ops"), dict) else {}

    domains = [
        {
            "id": "gateway-wan",
            "title": "Gateway / WAN",
            "plain_description": "家庭网络第一层。它不正常时，DNS、Proxy、Kuma、Cloudflare 的异常都可能只是连带结果。",
            "status": domain_status("gateway-wan", ["gateway", "wan", "openwrt", "dhcp", "pppoe", "internet"]),
            "scope": f"{gateway or 'gateway'} / {lan.get('cidr') or 'LAN'}",
            "primary_owner": "OpenWrt Gateway",
            "first_probe": service("openwrt-luci").get("local_url") or gateway,
            "second_probe": "OpenWrt WAN interface, DHCP leases, client gateway/DNS",
            "healthy_when": ["OpenWrt direct IP responds.", "WAN session/carrier is up and counters move.", "A LAN client receives the expected gateway and DNS."],
            "if_bad": "Stop checking Pi services and remote domains; inspect OpenWrt WAN/LAN/DHCP first.",
            "source_tools": ["OpenWrt LuCI", "OpenWrt SSH", "ISP modem/admin page"],
            "entries": first_entries("openwrt-luci", "openwrt-ssh"),
            "services": [service("openwrt-luci"), service("openwrt-ssh")],
            "remote_pairs": [],
            "live_evidence": domain_live_evidence("gateway-wan"),
        },
        {
            "id": "wifi-radio",
            "title": "Wi-Fi Radios / SSIDs",
            "plain_description": "验证 SSID、radio 和客户端关联；覆盖断电来电后 5G 不起、Wi-Fi 无互联网、信号差。",
            "status": domain_status("wifi-radio", ["wifi", "wireless", "radio", "ssid", "5ghz", "5g", "rssi"]),
            "scope": f"main={main_wifi.get('ssid') or '-'} backhaul={relay_wifi.get('ssid') or '-'}",
            "primary_owner": "OpenWrt wireless config",
            "first_probe": service("openwrt-luci").get("local_url") or gateway,
            "second_probe": "wireless status, SSID broadcast, association/RSSI, DHCP lease",
            "healthy_when": ["Expected SSIDs are broadcasting on intended radios.", "Client is associated to the expected AP/radio.", "Client receives a lease from the expected network."],
            "if_bad": "Inspect radio state and client association before touching DNS or Proxy.",
            "source_tools": ["OpenWrt wireless status", "client Wi-Fi diagnostics"],
            "entries": first_entries("openwrt-luci", "openwrt-ssh"),
            "services": [service("openwrt-luci")],
            "remote_pairs": [],
            "live_evidence": domain_live_evidence("wifi-radio"),
        },
        {
            "id": "room-ap",
            "title": "Room AP / Bedroom Coverage",
            "plain_description": "卧室覆盖层。它应改善卧室信号，但不应该成为第二个 DHCP authority。",
            "status": domain_status("room-ap", ["room", "relay", "backhaul", "wrt-room", "room-ap"]),
            "scope": room_host or "room AP",
            "primary_owner": "Room AP LuCI/SSH",
            "first_probe": service("wrt-room-luci").get("local_url") or room_host,
            "second_probe": "Room AP upstream/backhaul, DHCP disabled, client lease source",
            "healthy_when": ["Room AP management IP responds.", "Room AP upstream/backhaul is associated and stable.", "Room clients still obtain DHCP from the gateway."],
            "if_bad": "Localize the issue to Room AP/backhaul; avoid global Wi-Fi redesign.",
            "source_tools": ["WRT Room LuCI", "WRT Room SSH", "OpenWrt wireless status"],
            "entries": first_entries("wrt-room-luci", "wrt-room-ssh", "openwrt-luci"),
            "services": [service("wrt-room-luci"), service("wrt-room-ssh")],
            "remote_pairs": [],
            "live_evidence": domain_live_evidence("room-ap"),
        },
        {
            "id": "dns-proxy",
            "title": "DNS / Proxy",
            "plain_description": "拆开 DNS answer、规则命中、代理组健康度。国内慢、国外慢、AI 节点走错组都从这里定位。",
            "status": domain_status("dns-proxy", ["dns", "adguard", "mihomo", "proxy", "tproxy", "fake-ip", "rule"]),
            "scope": f"{service('adguard').get('host') or server_host} + {service('mihomo').get('host') or server_host}",
            "primary_owner": "AdGuard DNS + Mihomo Proxy",
            "first_probe": service("mihomo").get("local_url") or service("adguard").get("local_url") or server_host,
            "second_probe": "domestic DNS result, foreign DNS/fake-ip result, Mihomo rule and selected group",
            "healthy_when": ["Domestic domains resolve and route direct.", "Foreign/AI traffic matches intended rules.", "Selected proxy group has healthy candidates."],
            "if_bad": "Change only the owning layer: DNS answer problem in AdGuard/router DNS, route/group problem in Mihomo.",
            "source_tools": ["AdGuard Home", "Mihomo Dashboard/API", "OpenWrt policy routing"],
            "entries": first_entries("adguard", "mihomo", "openwrt-ssh"),
            "services": [service("adguard"), service("mihomo")],
            "remote_pairs": [item for item in [remote_pair("mihomo")] if item],
            "live_evidence": domain_live_evidence("dns-proxy"),
        },
        {
            "id": "server-runtime",
            "title": "Server Runtime",
            "plain_description": "Pi/mini server 托管的服务层。多个服务一起掉时，先按一个 runtime 事件处理。",
            "status": domain_status("server-runtime", ["docker", "systemd", "server", "pi", "container", "port"]),
            "scope": server_host or "server",
            "primary_owner": "Server SSH + Docker/systemd",
            "first_probe": service("pi-ssh").get("host") or server_host,
            "second_probe": "docker ps, systemd units, listening ports, disk, memory",
            "healthy_when": ["Server host responds by direct LAN IP/SSH.", "Core containers and timers are running.", "Expected ports listen locally before checking remote domains."],
            "if_bad": "Do not edit Cloudflare or service rules until local runtime health is known.",
            "source_tools": ["Pi/server SSH", "Docker", "systemd"],
            "entries": first_entries("pi-ssh", "homenet-ops", "uptime-kuma"),
            "services": [service("homenet-ops"), service("uptime-kuma"), service("home-assistant"), service("adguard"), service("mihomo")],
            "remote_pairs": [item for item in [remote_pair("homenet-ops"), remote_pair("uptime-kuma"), remote_pair("home-assistant")] if item],
            "live_evidence": domain_live_evidence("server-runtime"),
        },
        {
            "id": "remote-access",
            "title": "Remote Access",
            "plain_description": "外部入口层。先证明对应 LAN target 正常，再看 Cloudflare Tunnel/Access、Caddy/DDNS 或 WireGuard。",
            "status": domain_status("remote-access", ["remote", "cloudflare", "tunnel", "access", "caddy", "wireguard", "ddns"]),
            "scope": f"{len(remote_entries)} remote entries",
            "primary_owner": "Cloudflare / Caddy / WireGuard",
            "first_probe": service("homenet-ops").get("local_url") or server_host,
            "second_probe": "paired remote URL, tunnel/access state, Caddy/DDNS, WireGuard peer",
            "healthy_when": ["Paired LAN target works first.", "The matching remote entry reaches that target.", "Kuma or provider state agrees with the expected public entry."],
            "if_bad": "If the LAN target is down, go back to Server Runtime; if LAN is healthy, inspect the matching remote owner.",
            "source_tools": ["Cloudflare Dashboard/API", "cloudflared", "Caddy/DDNS", "WireGuard", "Kuma"],
            "entries": first_entries("homenet-ops", "pi-ssh", "wireguard"),
            "services": [service("cloudflared"), service("caddy"), service("wireguard"), service("ddns-go")],
            "remote_pairs": [item for item in [remote_pair("homenet-ops"), remote_pair("uptime-kuma"), remote_pair("home-assistant"), remote_pair("wireguard")] if item],
            "live_evidence": domain_live_evidence("remote-access"),
        },
        {
            "id": "smart-home",
            "title": "Smart Home / Apple Home",
            "plain_description": "智能家居控制层。Apple Home 无响应时，先证明 HA、HomeKit Bridge 和 Home Hub；需要时再打开 mDNS 深查。",
            "status": domain_status("smart-home", ["apple home", "homekit", "home hub", "airplay", "home assistant", "mqtt", "zigbee"]),
            "scope": f"HA={service('home-assistant').get('host') or server_host} HomeKit=21064",
            "primary_owner": "Home Assistant + Apple Home Hub",
            "first_probe": service("home-assistant").get("local_url") or server_host,
            "second_probe": "HomeKit Bridge TCP 21064, Apple TV/Home Hub control ports, optional mDNS discovery",
            "healthy_when": ["Home Assistant is reachable locally.", "HomeKit Bridge listens on its declared port.", "Apple TV/Home Hub is on LAN and reachable from HA."],
            "if_bad": "Fix HA/HomeKit/Home Hub first; do not change WAN, proxy, DNS, or whole Wi-Fi for an Apple Home-only symptom.",
            "source_tools": ["Home Assistant", "Apple Home app", "Apple TV/Home Hub", "OpenWrt DHCP/wireless"],
            "entries": first_entries("home-assistant", "homekit-bridge", "openwrt-luci"),
            "services": [service("home-assistant"), service("homekit-bridge"), service("mosquitto"), service("zigbee2mqtt")],
            "remote_pairs": [item for item in [remote_pair("home-assistant")] if item],
            "live_evidence": domain_live_evidence("smart-home"),
        },
        {
            "id": "rescue-path",
            "title": "Rescue / Maintenance Path",
            "plain_description": "低依赖检修通道。它应该绕开家庭 DNS/Proxy 的复杂路径，让维护设备仍能进 OpenWrt/Pi。",
            "status": domain_status("rescue-path", ["rescue", "ops", "maintenance"]),
            "scope": f"{ops.get('cidr') or maintenance.get('cidr') or '-'} / {maintenance_wifi.get('ssid') or 'Maintenance SSID'}",
            "primary_owner": "Maintenance Wi-Fi + OpenWrt firewall/DHCP",
            "first_probe": str(maintenance.get("gateway") or ops.get("gateway") or ""),
            "second_probe": "direct WAN from Maintenance network, direct IP access to Pi/OpenWrt",
            "healthy_when": ["Maintenance device can join the Maintenance path.", "It can reach the internet independently enough for operator tools.", "It can reach Pi/OpenWrt by direct IP."],
            "if_bad": "Keep this path small; fix only SSID/DHCP/firewall reachability needed for maintenance.",
            "source_tools": ["OpenWrt LuCI/SSH", "Pi SSH", "HomeNet"],
            "entries": first_entries("openwrt-luci", "openwrt-ssh", "pi-ssh", "homenet-ops"),
            "services": [service("openwrt-luci"), service("pi-ssh"), service("homenet-ops")],
            "remote_pairs": [],
            "live_evidence": domain_live_evidence("rescue-path"),
        },
        {
            "id": "client-device",
            "title": "Client / Device Identity",
            "plain_description": "单设备身份层。Apple 私有 MAC、IoT 重新入网、固定 IP 错位、hostname 解析异常都在这里处理。",
            "status": domain_status("client-device", ["lease", "dhcp", "device", "client", "hostname", "mac", "local", "lan"]),
            "scope": "DHCP leases, static mappings, hostnames, SSID-specific MACs",
            "primary_owner": "OpenWrt DHCP/static leases + device native settings",
            "first_probe": service("openwrt-luci").get("local_url") or gateway,
            "second_probe": "current lease, static binding, SSID-specific MAC, device power/sleep state",
            "healthy_when": ["Observed MAC matches the SSID-specific binding.", "The device lease/IP matches declared intent.", "The hostname points to the stable target for that device."],
            "if_bad": "Fix the device identity or binding; do not change whole-network routing for a single device.",
            "source_tools": ["OpenWrt DHCP/static leases", "device settings", "Home Assistant", "HomeNet instance files"],
            "entries": first_entries("openwrt-luci", "homenet-ops"),
            "services": [],
            "remote_pairs": [],
            "live_evidence": domain_live_evidence("client-device"),
        },
    ]

    status_counts: dict[str, int] = {}
    for domain in domains:
        status_value = str(domain.get("status") or "unknown")
        status_counts[status_value] = status_counts.get(status_value, 0) + 1

    if live and not [domain for domain in domains if str(domain.get("status") or "") in {"bad", "warn"}]:
        headline = "All diagnostic domains are healthy from the current read-only evidence."
    elif live_summary.get("checked"):
        headline = "Use the first bad or warning diagnostic domain as the starting point."
    else:
        headline = "Offline diagnostic map. Run with --live from a trusted maintenance host to prove current state."

    return {
        "schema": "homenet.diagnostic_surface.v1",
        "live": live,
        "headline": headline,
        "summary": {
            "domains": len(domains),
            "status_counts": dict(sorted(status_counts.items())),
            "first_probes": sum(1 for domain in domains if domain.get("first_probe")),
            "live_findings": len(top_findings),
            "classified_findings": len(classified_findings),
            "domains_with_live_findings": sum(1 for counts in domain_counts.values() if isinstance(counts, dict) and (int(counts.get("fail") or 0) or int(counts.get("warn") or 0))),
            "services_referenced": len({
                str(service_item.get("id") or "")
                for domain in domains
                for service_item in as_list(domain.get("services"))
                if isinstance(service_item, dict) and service_item.get("id")
            }),
            "remote_pairs": sum(len(as_list(domain.get("remote_pairs"))) for domain in domains),
        },
        "domains": domains,
        "operator_rule": "Start with the lowest layer that is not proven healthy: Rescue path, Gateway/WAN, Wi-Fi/Room AP, DNS/Proxy, Server runtime, Remote access, then individual devices.",
        "privacy": {
            "secrets_included": False,
            "secret_values_checked": False,
            "note": "The diagnostic surface contains targets, owners, and URLs only; it must not include passwords, tokens, keys, cookies, sessions, or subscription URLs.",
        },
    }
