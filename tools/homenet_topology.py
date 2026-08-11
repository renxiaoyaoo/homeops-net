from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def build_topology_from_metadata(metadata: dict[str, Any], instance: Path, as_list: Callable[[Any], list[Any]]) -> dict[str, Any]:
    runtime = metadata.get("runtime_targets", {}) if isinstance(metadata.get("runtime_targets"), dict) else {}
    networks = metadata.get("networks", {}) if isinstance(metadata.get("networks"), dict) else {}
    wifi = metadata.get("wifi", {}) if isinstance(metadata.get("wifi"), dict) else {}
    devices = [item for item in metadata.get("devices", []) if isinstance(item, dict)]
    services = [item for item in metadata.get("service_directory", []) if isinstance(item, dict)]
    remote_ingress = [item for item in metadata.get("remote_ingress", []) if isinstance(item, dict)]

    gateway_host = str(runtime.get("openwrt_gateway") or "")
    server = runtime.get("server", {}) if isinstance(runtime.get("server"), dict) else {}
    server_host = str(server.get("host") or "")
    room_ap = runtime.get("room_ap", {}) if isinstance(runtime.get("room_ap"), dict) else {}
    room_ap_host = str(room_ap.get("host") or "")

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    def add_node(node_id: str, label: str, node_type: str, **extra: Any) -> None:
        if not any(item.get("id") == node_id for item in nodes):
            nodes.append({"id": node_id, "label": label, "type": node_type, **extra})

    def add_edge(source: str, target: str, label: str, edge_type: str, **extra: Any) -> None:
        edges.append({"source": source, "target": target, "label": label, "type": edge_type, **extra})

    add_node("internet", "Internet / WAN", "external", role="Upstream connectivity")
    if gateway_host:
        add_node("gateway", "OpenWrt Gateway", "runtime", host=gateway_host, role="Gateway, DHCP, firewall, Wi-Fi, TProxy handoff")
        add_edge("internet", "gateway", "WAN uplink", "wan")
    if server_host:
        add_node("server", "Server Runtime", "runtime", host=server_host, role=server.get("role") or "Server runtime")
        if gateway_host:
            add_edge("gateway", "server", "LAN service host", "lan")
    if room_ap_host:
        add_node("room-ap", "Room AP / Relay", "runtime", host=room_ap_host, role=room_ap.get("role") or "Coverage AP")
        if gateway_host:
            add_edge("gateway", "room-ap", "LAN bridge / upstream", "lan")

    node_ids: set[str] = {str(node.get("id") or "") for node in nodes}
    for network_id, network in networks.items():
        if not isinstance(network, dict) or network.get("enabled") is False:
            continue
        node_id = f"network:{network_id}"
        add_node(
            node_id,
            f"{network_id} {network.get('cidr', '')}".strip(),
            "network",
            cidr=network.get("cidr") or "",
            gateway=network.get("gateway") or "",
            dns_mode=network.get("dns_mode") or "",
            proxy_mode=network.get("proxy_mode") or "",
            purpose=network.get("purpose") or "",
        )
        node_ids.add(node_id)
        if gateway_host:
            add_edge("gateway", node_id, "routes / DHCP / firewall", "network")

    for wifi_id, item in wifi.items():
        if not isinstance(item, dict):
            continue
        node_id = f"wifi:{wifi_id}"
        network_id = str(item.get("network") or "")
        add_node(
            node_id,
            str(item.get("ssid") or wifi_id),
            "wifi",
            band=item.get("band") or "",
            network=network_id,
            purpose=item.get("purpose") or "",
            broadcast_by=as_list(item.get("broadcast_by")),
        )
        node_ids.add(node_id)
        if network_id and f"network:{network_id}" in node_ids:
            add_edge(node_id, f"network:{network_id}", "bridges to network", "ssid-network")
        for broadcaster in as_list(item.get("broadcast_by")):
            b_name = str(broadcaster).lower()
            source = "room-ap" if "wrt room" in b_name or "room" in b_name else "gateway"
            if source in node_ids:
                add_edge(source, node_id, "broadcasts SSID", "wireless")

    for device in devices:
        device_id = str(device.get("id") or "")
        if not device_id:
            continue
        node_id = f"device:{device_id}"
        network_id = str(device.get("network") or "")
        add_node(
            node_id,
            str(device.get("name") or device_id),
            "device",
            ip=device.get("ip") or "",
            network=network_id,
            role=device.get("role") or "",
            expected=device.get("expected", True),
        )
        if network_id and f"network:{network_id}" in node_ids:
            add_edge(f"network:{network_id}", node_id, "assigned / connected", "device-network")

    for service in services:
        service_id = str(service.get("id") or "")
        if not service_id:
            continue
        node_id = f"service:{service_id}"
        runtime_target = str(service.get("runtime") or "")
        host = str(service.get("host") or "")
        add_node(
            node_id,
            str(service.get("name") or service_id),
            "service",
            category=service.get("category") or "",
            runtime=runtime_target,
            host=host,
            role=service.get("role") or "",
            local_url=service.get("local_url") or "",
            remote_url=service.get("remote_url") or "",
        )
        node_ids.add(node_id)
        if host == room_ap_host:
            owner_node = "room-ap"
        elif runtime_target == "openwrt" or host == gateway_host:
            owner_node = "gateway"
        else:
            owner_node = "server"
        if owner_node in node_ids:
            add_edge(owner_node, node_id, "hosts / owns entry", "service-host")

    for entry in remote_ingress:
        entry_id = str(entry.get("id") or "")
        if not entry_id:
            continue
        node_id = f"remote:{entry_id}"
        service_id = str(entry.get("service_id") or "")
        add_node(
            node_id,
            str(entry.get("name") or entry_id),
            "remote-ingress",
            kind=entry.get("kind") or "",
            href=entry.get("href") or "",
            target=entry.get("target") or "",
            status_source=entry.get("status_source") or "",
            service_id=service_id,
        )
        add_edge("internet", node_id, "external entry", "remote")
        if service_id and f"service:{service_id}" in node_ids:
            add_edge(node_id, f"service:{service_id}", "forwards to service", "remote-target")

    traffic_paths = [
        {"id": "home-lan-default", "title": "Home LAN default path", "path": ["Client on main SSID/LAN", "OpenWrt Gateway", "AdGuard DNS on server runtime", "Mihomo policy if traffic needs proxy", "Internet or LAN service"], "purpose": "Daily home traffic with home DNS and transparent proxy policy."},
        {"id": "domestic-direct", "title": "Domestic direct path", "path": ["Client", "OpenWrt Gateway", "AdGuard real DNS", "DIRECT WAN"], "purpose": "Domestic apps should stay direct and fast."},
        {"id": "foreign-proxy", "title": "Foreign / AI proxy path", "path": ["Client", "OpenWrt TProxy", "Mihomo on server runtime", "selected proxy group", "Internet"], "purpose": "Foreign and AI services should work without manual toggling at home."},
        {"id": "explicit-proxy", "title": "Explicit proxy path", "path": ["Client configured with proxy", "Mihomo mixed proxy port", "selected proxy group", "Internet"], "purpose": "Fallback for clients or apps that need an explicit proxy endpoint."},
        {"id": "remote-web", "title": "Remote web service path", "path": ["Outside client", "Cloudflare Access/Tunnel or IPv6 direct", "server runtime", "selected LAN service"], "purpose": "Selected web services are reachable outside home without exposing the whole LAN."},
        {"id": "return-home", "title": "Return-home LAN path", "path": ["Outside device", "WireGuard", "server runtime", "LAN routes", "home devices/services"], "purpose": "Device-to-LAN access for maintenance and home services outside home."},
        {"id": "ops-maintenance", "title": "Maintenance path", "path": ["Operator device", "Maintenance SSID", "OpenWrt Gateway", "direct WAN + limited server access"], "purpose": "Low-dependency maintenance path when home DNS/proxy is unhealthy."},
        {"id": "room-coverage", "title": "Room coverage path", "path": ["Bedroom client", "WRT Room AP/Relay", "OpenWrt Gateway", "LAN/Internet"], "purpose": "Bedroom coverage without adding another DHCP authority."},
        {"id": "iot-smart-home", "title": "IoT / smart-home path", "path": ["IoT device", "IoT SSID/network", "OpenWrt Gateway", "Home Assistant / MQTT / Zigbee services"], "purpose": "IoT devices stay on the IoT network while services run on the server runtime."},
    ]

    by_type: dict[str, int] = {}
    by_edge_type: dict[str, int] = {}
    services_by_runtime: dict[str, int] = {}
    services_by_category: dict[str, int] = {}
    for node in nodes:
        node_type = str(node.get("type") or "unknown")
        by_type[node_type] = by_type.get(node_type, 0) + 1
    for edge in edges:
        edge_type = str(edge.get("type") or "unknown")
        by_edge_type[edge_type] = by_edge_type.get(edge_type, 0) + 1
    for service in services:
        runtime_target = str(service.get("runtime") or "unknown")
        category = str(service.get("category") or "other")
        services_by_runtime[runtime_target] = services_by_runtime.get(runtime_target, 0) + 1
        services_by_category[category] = services_by_category.get(category, 0) + 1

    return {
        "schema": "homenet.topology.v1",
        "instance": metadata.get("instance") or {},
        "instance_path": str(instance),
        "profile": metadata.get("profile"),
        "read_only": True,
        "writes_files": False,
        "writes_live_config": False,
        "summary": {
            "nodes": len(nodes),
            "edges": len(edges),
            "networks": len([n for n in nodes if n.get("type") == "network"]),
            "wifi": len([n for n in nodes if n.get("type") == "wifi"]),
            "devices": len([n for n in nodes if n.get("type") == "device"]),
            "services": len([n for n in nodes if n.get("type") == "service"]),
            "remote_ingress": len([n for n in nodes if n.get("type") == "remote-ingress"]),
            "traffic_paths": len(traffic_paths),
        },
        "by_type": dict(sorted(by_type.items())),
        "by_edge_type": dict(sorted(by_edge_type.items())),
        "services_by_runtime": dict(sorted(services_by_runtime.items())),
        "services_by_category": dict(sorted(services_by_category.items())),
        "nodes": nodes,
        "edges": edges,
        "traffic_paths": traffic_paths,
        "operator_rules": [
            "Topology describes declared architecture, not live proof. Use status/check --live for current evidence.",
            "Gateway owns network boundaries, DHCP, firewall, Wi-Fi, and TProxy handoff.",
            "Server runtime hosts richer DNS, Proxy, monitoring, remote access, and home services when enabled.",
            "Room AP improves coverage; it should not become a second DHCP authority in this model.",
            "Maintenance Wi-Fi is a maintenance path and should stay independent from the home DNS/proxy stack.",
        ],
        "privacy": {
            "secrets_included": False,
            "secret_values_checked": False,
            "live_state_read": False,
            "note": "Topology uses declared metadata only and excludes Wi-Fi passwords, tokens, private keys, cookies, sessions, and proxy subscription URLs.",
        },
    }


def print_topology_markdown(topology: dict[str, Any], as_list: Callable[[Any], list[Any]]) -> None:
    instance = topology.get("instance", {})
    name = instance.get("display_name") or instance.get("name") or Path(str(topology.get("instance_path", "instance"))).name
    print(f"# Network Topology - {name}")
    print()
    print(f"- schema: `{topology.get('schema')}`")
    print(f"- profile: `{topology.get('profile')}`")
    print(f"- read only: {topology.get('read_only')}")
    print(f"- writes files: {topology.get('writes_files')}")
    print(f"- writes live config: {topology.get('writes_live_config')}")
    print()
    print("## Summary")
    print()
    for key, value in topology.get("summary", {}).items():
        print(f"- {key}: {value}")
    print()
    print("## Runtime Graph")
    print()
    print("| Source | Target | Link | Type |")
    print("| --- | --- | --- | --- |")
    node_labels = {
        str(node.get("id") or ""): str(node.get("label") or node.get("id") or "")
        for node in topology.get("nodes", [])
        if isinstance(node, dict)
    }
    for edge in topology.get("edges", []):
        if not isinstance(edge, dict):
            continue
        edge_type = str(edge.get("type") or "")
        if edge_type not in {"wan", "lan", "network", "wireless", "ssid-network", "remote", "remote-target"}:
            continue
        source = node_labels.get(str(edge.get("source") or ""), str(edge.get("source") or ""))
        target = node_labels.get(str(edge.get("target") or ""), str(edge.get("target") or ""))
        print(f"| {source} | {target} | {edge.get('label', '')} | {edge_type} |")
    print()
    print("## Networks")
    print()
    print("| Network | CIDR | Gateway | DNS | Proxy | Purpose |")
    print("| --- | --- | --- | --- | --- | --- |")
    for node in topology.get("nodes", []):
        if isinstance(node, dict) and node.get("type") == "network":
            print(
                f"| {node.get('label', '')} | {node.get('cidr', '')} | {node.get('gateway', '')} | "
                f"{node.get('dns_mode', '')} | {node.get('proxy_mode', '')} | {node.get('purpose', '')} |"
            )
    print()
    print("## Wi-Fi")
    print()
    print("| SSID | Network | Band | Broadcast By | Purpose |")
    print("| --- | --- | --- | --- | --- |")
    for node in topology.get("nodes", []):
        if isinstance(node, dict) and node.get("type") == "wifi":
            print(
                f"| {node.get('label', '')} | {node.get('network', '')} | {node.get('band', '')} | "
                f"{', '.join(as_list(node.get('broadcast_by')))} | {node.get('purpose', '')} |"
            )
    print()
    print("## Service Placement")
    print()
    print("### By Runtime")
    print()
    for runtime, count in topology.get("services_by_runtime", {}).items():
        print(f"- `{runtime}`: {count}")
    print()
    print("### By Category")
    print()
    for category, count in topology.get("services_by_category", {}).items():
        print(f"- `{category}`: {count}")
    print()
    print("## Remote Ingress")
    print()
    print("| Entry | Kind | Target | Service | Status Source |")
    print("| --- | --- | --- | --- | --- |")
    for node in topology.get("nodes", []):
        if isinstance(node, dict) and node.get("type") == "remote-ingress":
            print(
                f"| {node.get('label', '')} | {node.get('kind', '')} | {node.get('target', '')} | "
                f"{node.get('service_id', '')} | {node.get('status_source', '')} |"
            )
    print()
    print("## Traffic Paths")
    print()
    for path in topology.get("traffic_paths", []):
        if not isinstance(path, dict):
            continue
        print(f"### {path.get('title')}")
        print()
        print(f"- purpose: {path.get('purpose')}")
        print(f"- path: {' -> '.join(as_list(path.get('path')))}")
        print()
    print("## Operator Rules")
    print()
    for rule in topology.get("operator_rules", []):
        print(f"- {rule}")
    print()
