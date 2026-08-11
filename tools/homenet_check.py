from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import yaml
except ImportError:  # pragma: no cover - kept for clear operator feedback
    yaml = None


ROOT = Path(__file__).resolve().parents[1]
SECRET_RE = re.compile(
    r"(password|passwd|token|secret|private[_-]?key|subscription|cookie|session)",
    re.IGNORECASE,
)
MAC_RE = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")
HOSTNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,251}[A-Za-z0-9]$")
@dataclass
class Finding:
    level: str
    area: str
    message: str


class Reporter:
    def __init__(self) -> None:
        self.findings: list[Finding] = []

    def ok(self, area: str, message: str) -> None:
        self.findings.append(Finding("OK", area, message))

    def warn(self, area: str, message: str) -> None:
        self.findings.append(Finding("WARN", area, message))

    def fail(self, area: str, message: str) -> None:
        self.findings.append(Finding("FAIL", area, message))

    @property
    def failed(self) -> bool:
        return any(f.level == "FAIL" for f in self.findings)

    def print(self) -> None:
        width = max((len(f.area) for f in self.findings), default=4)
        for finding in self.findings:
            print(f"{finding.level:<4} {finding.area:<{width}} {finding.message}")
        fails = sum(1 for f in self.findings if f.level == "FAIL")
        warns = sum(1 for f in self.findings if f.level == "WARN")
        print(f"\nSummary: failures={fails} warnings={warns}")


def load_yaml(path: Path) -> Any:
    if yaml is None:
        raise RuntimeError("PyYAML is required. Install python3-yaml or PyYAML.")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def ip_in_network(ip_value: str, cidr: str) -> bool:
    return ipaddress.ip_address(ip_value) in ipaddress.ip_network(cidr, strict=False)


def is_ipv4(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def collect_secret_paths(value: Any, prefix: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{prefix}.{key}" if prefix else str(key)
            if SECRET_RE.search(str(key)):
                hits.append(child_path)
            hits.extend(collect_secret_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(collect_secret_paths(child, f"{prefix}[{index}]"))
    return hits


def parse_enum(type_name: str) -> set[str] | None:
    match = re.fullmatch(r"enum\((.*)\)", type_name.strip())
    if not match:
        return None
    return {item.strip() for item in match.group(1).split(",") if item.strip()}


def valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return bool(parsed.scheme and (parsed.netloc or parsed.scheme in {"udp"}))


def valid_ipv4_or_hostname(value: str) -> bool:
    if is_ipv4(value):
        return True
    return bool(HOSTNAME_RE.match(value))


def validate_scalar(value: Any, type_name: str, path: str, reporter: Reporter) -> None:
    enum_values = parse_enum(type_name)
    if enum_values is not None:
        if str(value) not in enum_values:
            reporter.fail("schema", f"{path} must be one of {', '.join(sorted(enum_values))}")
        return

    if type_name == "string":
        if not isinstance(value, str):
            reporter.fail("schema", f"{path} must be string")
    elif type_name == "bool":
        if not isinstance(value, bool):
            reporter.fail("schema", f"{path} must be bool")
    elif type_name == "bool_or_auto":
        if not (isinstance(value, bool) or value == "auto"):
            reporter.fail("schema", f"{path} must be bool or auto")
    elif type_name == "ipv4":
        if not isinstance(value, str) or not is_ipv4(value):
            reporter.fail("schema", f"{path} must be ipv4")
    elif type_name == "cidr":
        try:
            ipaddress.ip_network(str(value), strict=False)
        except ValueError:
            reporter.fail("schema", f"{path} must be cidr")
    elif type_name == "url":
        if not isinstance(value, str) or not valid_url(value):
            reporter.fail("schema", f"{path} must be url")
    elif type_name == "ipv4_or_hostname":
        if not isinstance(value, str) or not valid_ipv4_or_hostname(value):
            reporter.fail("schema", f"{path} must be ipv4_or_hostname")
    elif type_name == "list_string":
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            reporter.fail("schema", f"{path} must be list_string")
    elif type_name == "list_mac":
        if not isinstance(value, list):
            reporter.fail("schema", f"{path} must be list_mac")
            return
        for index, item in enumerate(value):
            if not isinstance(item, str) or not MAC_RE.match(item.lower()):
                reporter.fail("schema", f"{path}[{index}] must be mac")
    else:
        reporter.warn("schema", f"{path} has unsupported schema type {type_name}")


def validate_schema_node(value: Any, schema: dict[str, Any], path: str, reporter: Reporter) -> None:
    node_type = schema.get("type")
    if isinstance(node_type, str):
        if node_type == "list":
            if not isinstance(value, list):
                reporter.fail("schema", f"{path} must be list")
                return
            item_schema = schema.get("item")
            if isinstance(item_schema, dict):
                for index, item in enumerate(value):
                    validate_schema_node(item, item_schema, f"{path}[{index}]", reporter)
            return
        validate_scalar(value, node_type, path, reporter)
        return

    if "fields" in schema or "pattern_fields" in schema or "required" in schema:
        if not isinstance(value, dict):
            reporter.fail("schema", f"{path} must be mapping")
            return
        for key in as_list(schema.get("required")):
            if key not in value:
                reporter.fail("schema", f"{path}.{key} is required")
        fields = schema.get("fields") if isinstance(schema.get("fields"), dict) else {}
        for key, child_schema in fields.items():
            if key in value and isinstance(child_schema, dict):
                validate_schema_node(value[key], child_schema, f"{path}.{key}", reporter)
            elif key in value and isinstance(child_schema, str):
                validate_scalar(value[key], child_schema, f"{path}.{key}", reporter)
        pattern_fields = schema.get("pattern_fields") if isinstance(schema.get("pattern_fields"), dict) else {}
        wildcard = pattern_fields.get("*")
        if isinstance(wildcard, dict):
            for key, child in value.items():
                validate_schema_node(child, wildcard, f"{path}.{key}", reporter)


def validate_document_schema(doc: dict[str, Any], schema_name: str, reporter: Reporter) -> None:
    before_failures = sum(1 for finding in reporter.findings if finding.level == "FAIL")
    schema_path = ROOT / "schemas" / schema_name
    if not schema_path.exists():
        reporter.warn("schema", f"{schema_name} missing")
        return
    try:
        schema = load_yaml(schema_path)
    except Exception as exc:  # noqa: BLE001
        reporter.fail("schema", f"{schema_name} cannot be parsed: {exc}")
        return
    if not isinstance(schema, dict):
        reporter.fail("schema", f"{schema_name} must be mapping")
        return
    validate_schema_node(doc, schema, schema_name.removesuffix(".schema.yaml"), reporter)
    after_failures = sum(1 for finding in reporter.findings if finding.level == "FAIL")
    if after_failures == before_failures:
        reporter.ok("schema", f"{schema_name} applied")


def require_file(instance: Path, name: str, reporter: Reporter) -> dict[str, Any]:
    path = instance / name
    if not path.exists():
        reporter.fail("instance", f"{name} missing")
        return {}
    try:
        data = load_yaml(path)
    except Exception as exc:  # noqa: BLE001 - command should report all parse errors
        reporter.fail("instance", f"{name} cannot be parsed: {exc}")
        return {}
    if not isinstance(data, dict):
        reporter.fail("instance", f"{name} must be a YAML mapping")
        return {}
    reporter.ok("instance", f"{name} parsed")
    return data


def check_instance(instance: Path, reporter: Reporter) -> dict[str, Any]:
    site = require_file(instance, "site.yaml", reporter)
    devices_doc = require_file(instance, "devices.yaml", reporter)
    services_doc = require_file(instance, "services.yaml", reporter)

    validate_document_schema(site, "site.schema.yaml", reporter)
    validate_document_schema(devices_doc, "devices.schema.yaml", reporter)
    validate_document_schema(services_doc, "services.schema.yaml", reporter)

    for name, doc in [
        ("site.yaml", site),
        ("devices.yaml", devices_doc),
        ("services.yaml", services_doc),
    ]:
        for path in collect_secret_paths(doc):
            reporter.fail("privacy", f"{name} contains secret-like key: {path}")

    networks = site.get("networks") if isinstance(site.get("networks"), dict) else {}
    wifi = site.get("wifi") if isinstance(site.get("wifi"), dict) else {}
    remote_ingress = site.get("remote_ingress") if isinstance(site.get("remote_ingress"), list) else []
    devices = devices_doc.get("devices") if isinstance(devices_doc.get("devices"), list) else []
    services = services_doc.get("services") if isinstance(services_doc.get("services"), list) else []

    check_site(site, networks, wifi, reporter)
    check_devices(devices, networks, reporter)
    check_services(services, devices, networks, reporter)
    check_remote_ingress(remote_ingress, services, reporter)

    return {
        "site": site,
        "networks": networks,
        "wifi": wifi,
        "remote_ingress": remote_ingress,
        "devices": devices,
        "services": services,
    }


def check_site(site: dict[str, Any], networks: dict[str, Any], wifi: dict[str, Any], reporter: Reporter) -> None:
    if site.get("schema") != "homenet.site.v1":
        reporter.fail("site", "schema must be homenet.site.v1")
    else:
        reporter.ok("site", "schema version is homenet.site.v1")

    router_host = site.get("runtime", {}).get("router", {}).get("host")
    if router_host:
        known_gateways = [n.get("gateway") for n in networks.values() if isinstance(n, dict)]
        if router_host in known_gateways:
            reporter.ok("site", f"router host {router_host} matches a network gateway")
        else:
            reporter.warn("site", f"router host {router_host} is not listed as a network gateway")

    for net_id, net in networks.items():
        if not isinstance(net, dict):
            reporter.fail("network", f"{net_id} must be a mapping")
            continue
        cidr = net.get("cidr")
        if not cidr:
            reporter.fail("network", f"{net_id} missing cidr")
            continue
        try:
            ipaddress.ip_network(cidr, strict=False)
            reporter.ok("network", f"{net_id} cidr {cidr} valid")
        except ValueError as exc:
            reporter.fail("network", f"{net_id} cidr invalid: {exc}")
            continue
        gateway = net.get("gateway")
        if gateway and not ip_in_network(gateway, cidr):
            reporter.fail("network", f"{net_id} gateway {gateway} outside {cidr}")

    for wifi_id, item in wifi.items():
        network = item.get("network") if isinstance(item, dict) else None
        ssid = item.get("ssid") if isinstance(item, dict) else None
        if not ssid:
            reporter.fail("wifi", f"{wifi_id} missing ssid")
        if network not in networks:
            reporter.fail("wifi", f"{wifi_id} references unknown network {network}")
        else:
            reporter.ok("wifi", f"{ssid} -> {network}")


def check_devices(devices: list[dict[str, Any]], networks: dict[str, Any], reporter: Reporter) -> None:
    seen_ids: set[str] = set()
    seen_ips: dict[str, str] = {}
    seen_macs: dict[str, str] = {}

    for device in devices:
        device_id = str(device.get("id", ""))
        if not device_id:
            reporter.fail("device", "device missing id")
            continue
        if device_id in seen_ids:
            reporter.fail("device", f"duplicate device id {device_id}")
        seen_ids.add(device_id)

        network_id = device.get("network")
        ip_value = device.get("ip")
        if network_id and network_id not in networks:
            reporter.fail("device", f"{device_id} references unknown network {network_id}")
        if ip_value:
            if not is_ipv4(str(ip_value)):
                reporter.fail("device", f"{device_id} has invalid IP {ip_value}")
            elif network_id in networks:
                cidr = networks[network_id].get("cidr")
                if cidr and not ip_in_network(str(ip_value), cidr):
                    reporter.fail("device", f"{device_id} IP {ip_value} outside {network_id} {cidr}")
                else:
                    reporter.ok("device", f"{device_id} fixed at {ip_value}")
            owner = seen_ips.get(str(ip_value))
            if owner and owner != device_id:
                reporter.fail("device", f"IP {ip_value} used by both {owner} and {device_id}")
            seen_ips[str(ip_value)] = device_id

        for mac in as_list(device.get("macs")):
            mac_l = str(mac).lower()
            if not MAC_RE.match(mac_l):
                reporter.fail("device", f"{device_id} has invalid MAC {mac}")
                continue
            owner = seen_macs.get(mac_l)
            if owner and owner != device_id:
                reporter.fail("device", f"MAC {mac_l} used by both {owner} and {device_id}")
            seen_macs[mac_l] = device_id


def check_services(
    services: list[dict[str, Any]],
    devices: list[dict[str, Any]],
    networks: dict[str, Any],
    reporter: Reporter,
) -> None:
    seen_ids: set[str] = set()
    known_ips = {str(d.get("ip")) for d in devices if d.get("ip")}
    known_gateways = {str(n.get("gateway")) for n in networks.values() if isinstance(n, dict) and n.get("gateway")}
    port_owners: dict[tuple[str, str, str], str] = {}

    for service in services:
        service_id = str(service.get("id", ""))
        if not service_id:
            reporter.fail("service", "service missing id")
            continue
        if service_id in seen_ids:
            reporter.fail("service", f"duplicate service id {service_id}")
        seen_ids.add(service_id)

        host = service.get("host")
        if host and is_ipv4(str(host)) and str(host) not in known_ips and str(host) not in known_gateways:
            reporter.warn("service", f"{service_id} host {host} is not in device inventory")

        has_entry = bool(service.get("local_url") or service.get("remote_url") or service.get("ports") or service.get("checks"))
        if has_entry:
            reporter.ok("service", f"{service_id} has an entry/check surface")
        else:
            reporter.warn("service", f"{service_id} has no URL, port, or check")

        for port in as_list(service.get("ports")):
            if not isinstance(port, dict):
                reporter.fail("service", f"{service_id} port entry must be a mapping")
                continue
            p_host = str(port.get("host") or host or "")
            p_port = str(port.get("port") or "")
            proto = str(port.get("proto") or "tcp").lower()
            if not p_host or not p_port:
                reporter.fail("service", f"{service_id} has incomplete port entry")
                continue
            key = (p_host, p_port, proto)
            owner = port_owners.get(key)
            if owner and owner != service_id:
                reporter.warn("service", f"{p_host}:{p_port}/{proto} shared by {owner} and {service_id}")
            port_owners[key] = service_id


def check_remote_ingress(remote_ingress: list[dict[str, Any]], services: list[dict[str, Any]], reporter: Reporter) -> None:
    service_ids = {str(service.get("id")) for service in services if isinstance(service, dict) and service.get("id")}
    seen_ids: set[str] = set()
    for entry in remote_ingress:
        if not isinstance(entry, dict):
            reporter.fail("ingress", "remote ingress entry must be a mapping")
            continue
        entry_id = str(entry.get("id") or "")
        if not entry_id:
            reporter.fail("ingress", "remote ingress entry missing id")
            continue
        if entry_id in seen_ids:
            reporter.fail("ingress", f"duplicate remote ingress id {entry_id}")
        seen_ids.add(entry_id)
        if not entry.get("name"):
            reporter.fail("ingress", f"{entry_id} missing name")
        if not entry.get("kind"):
            reporter.fail("ingress", f"{entry_id} missing kind")
        service_id = entry.get("service_id")
        if service_id and str(service_id) not in service_ids:
            reporter.warn("ingress", f"{entry_id} references unknown service {service_id}")
        reporter.ok("ingress", f"{entry_id} entry declared")
