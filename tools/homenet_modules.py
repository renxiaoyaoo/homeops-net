from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - kept for clear operator feedback
    yaml = None


ROOT = Path(__file__).resolve().parents[1]

MODULE_IDS = (
    "gateway-openwrt",
    "dns-layer",
    "proxy-mihomo",
    "remote-access",
    "observability-homenet",
    "smart-home",
    "maintenance-wifi",
    "server-runtime",
    "room-ap",
)

_MODULE_DEFINITIONS_CACHE: dict[str, Any] | None = None
_MODULE_ARTIFACTS_CACHE: dict[str, Any] | None = None
_MODULE_RENDERERS_CACHE: dict[str, Any] | None = None
_MODULE_IMPLEMENTATIONS_CACHE: dict[str, Any] | None = None
_MODULE_EXECUTORS_CACHE: dict[str, Any] | None = None
_MODULE_BACKUPS_CACHE: dict[str, Any] | None = None


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def load_yaml(path: Path) -> Any:
    if yaml is None:
        raise RuntimeError("PyYAML is required. Install python3-yaml or PyYAML.")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_module_definitions() -> dict[str, Any]:
    global _MODULE_DEFINITIONS_CACHE
    if _MODULE_DEFINITIONS_CACHE is not None:
        return _MODULE_DEFINITIONS_CACHE
    path = ROOT / "modules" / "catalog.yaml"
    if not path.exists():
        _MODULE_DEFINITIONS_CACHE = {
            "schema": "homenet.module_definitions.v1",
            "version": "",
            "module_count": 0,
            "modules": [],
            "errors": [f"{path.relative_to(ROOT)} is missing"],
        }
        return _MODULE_DEFINITIONS_CACHE
    data = load_yaml(path)
    if not isinstance(data, dict):
        _MODULE_DEFINITIONS_CACHE = {
            "schema": "homenet.module_definitions.v1",
            "version": "",
            "module_count": 0,
            "modules": [],
            "errors": [f"{path.relative_to(ROOT)} must contain a mapping"],
        }
        return _MODULE_DEFINITIONS_CACHE
    modules = [item for item in as_list(data.get("modules")) if isinstance(item, dict)]
    ids = [str(item.get("id") or "") for item in modules if item.get("id")]
    duplicates = sorted({module_id for module_id in ids if ids.count(module_id) > 1})
    declared_count = int(data.get("module_count") or 0)
    errors = [str(item) for item in as_list(data.get("errors")) if item]
    if declared_count and declared_count != len(modules):
        errors.append(f"module_count={declared_count} but modules={len(modules)}")
    if duplicates:
        errors.append(f"duplicate module IDs: {', '.join(duplicates)}")
    expected_ids = set(MODULE_IDS)
    missing_from_definitions = sorted(expected_ids - set(ids))
    extra_definitions = sorted(set(ids) - expected_ids)
    data["module_count"] = len(modules)
    data["modules"] = modules
    data["errors"] = errors
    data["missing_from_definitions"] = missing_from_definitions
    data["extra_definitions"] = extra_definitions
    data["ok"] = not errors and not missing_from_definitions
    data["source"] = str(path.relative_to(ROOT))
    _MODULE_DEFINITIONS_CACHE = data
    return _MODULE_DEFINITIONS_CACHE


def load_module_artifact_contracts() -> dict[str, Any]:
    global _MODULE_ARTIFACTS_CACHE
    if _MODULE_ARTIFACTS_CACHE is not None:
        return _MODULE_ARTIFACTS_CACHE
    path = ROOT / "modules" / "artifacts.yaml"
    if not path.exists():
        _MODULE_ARTIFACTS_CACHE = {
            "schema": "homenet.module_artifacts.v1",
            "version": "",
            "artifact_count": 0,
            "modules": {},
            "errors": [f"{path.relative_to(ROOT)} is missing"],
        }
        return _MODULE_ARTIFACTS_CACHE
    data = load_yaml(path)
    if not isinstance(data, dict):
        _MODULE_ARTIFACTS_CACHE = {
            "schema": "homenet.module_artifacts.v1",
            "version": "",
            "artifact_count": 0,
            "modules": {},
            "errors": [f"{path.relative_to(ROOT)} must contain a mapping"],
        }
        return _MODULE_ARTIFACTS_CACHE
    modules = data.get("modules") if isinstance(data.get("modules"), dict) else {}
    normalized: dict[str, list[dict[str, Any]]] = {}
    errors = [str(item) for item in as_list(data.get("errors")) if item]
    artifact_ids: list[str] = []
    for module_id, section in modules.items():
        if not isinstance(section, dict):
            errors.append(f"module {module_id} must contain a mapping")
            continue
        artifacts = [item for item in as_list(section.get("artifacts")) if isinstance(item, dict)]
        normalized[str(module_id)] = artifacts
        for artifact in artifacts:
            artifact_id = str(artifact.get("id") or "")
            if not artifact_id:
                errors.append(f"module {module_id} has an artifact without id")
                continue
            artifact_ids.append(f"{module_id}.{artifact_id}")
            for key in ("kind", "target", "path", "owner", "risk"):
                if not artifact.get(key):
                    errors.append(f"artifact {module_id}.{artifact_id} missing {key}")
    duplicates = sorted({artifact_id for artifact_id in artifact_ids if artifact_ids.count(artifact_id) > 1})
    if duplicates:
        errors.append(f"duplicate artifact IDs: {', '.join(duplicates)}")
    declared_count = int(data.get("artifact_count") or 0)
    if declared_count and declared_count != len(artifact_ids):
        errors.append(f"artifact_count={declared_count} but artifacts={len(artifact_ids)}")
    definitions = load_module_definitions()
    expected_modules = {
        str(item.get("id") or "")
        for item in as_list(definitions.get("modules"))
        if isinstance(item, dict) and item.get("id")
    } or set(MODULE_IDS)
    missing_modules = sorted(expected_modules - set(normalized.keys()))
    extra_modules = sorted(set(normalized.keys()) - expected_modules)
    data["modules"] = normalized
    data["artifact_count"] = len(artifact_ids)
    data["artifact_ids"] = sorted(artifact_ids)
    data["errors"] = errors
    data["missing_modules"] = missing_modules
    data["extra_modules"] = extra_modules
    data["ok"] = not errors and not missing_modules
    data["source"] = str(path.relative_to(ROOT))
    _MODULE_ARTIFACTS_CACHE = data
    return _MODULE_ARTIFACTS_CACHE


def load_module_renderer_contracts() -> dict[str, Any]:
    global _MODULE_RENDERERS_CACHE
    if _MODULE_RENDERERS_CACHE is not None:
        return _MODULE_RENDERERS_CACHE
    path = ROOT / "modules" / "renderers.yaml"
    if not path.exists():
        _MODULE_RENDERERS_CACHE = {
            "schema": "homenet.module_renderers.v1",
            "version": "",
            "renderer_count": 0,
            "modules": {},
            "errors": [f"{path.relative_to(ROOT)} is missing"],
        }
        return _MODULE_RENDERERS_CACHE
    data = load_yaml(path)
    if not isinstance(data, dict):
        _MODULE_RENDERERS_CACHE = {
            "schema": "homenet.module_renderers.v1",
            "version": "",
            "renderer_count": 0,
            "modules": {},
            "errors": [f"{path.relative_to(ROOT)} must contain a mapping"],
        }
        return _MODULE_RENDERERS_CACHE
    modules = data.get("modules") if isinstance(data.get("modules"), dict) else {}
    defaults = data.get("defaults") if isinstance(data.get("defaults"), dict) else {}
    normalized: dict[str, list[dict[str, Any]]] = {}
    errors = [str(item) for item in as_list(data.get("errors")) if item]
    renderer_ids: list[str] = []
    artifact_refs: list[str] = []
    artifact_contracts = load_module_artifact_contracts()
    known_artifacts = {
        str(item)
        for item in as_list(artifact_contracts.get("artifact_ids"))
        if str(item)
    }
    for module_id, section in modules.items():
        if not isinstance(section, dict):
            errors.append(f"module {module_id} must contain a mapping")
            continue
        renderers = [item for item in as_list(section.get("renderers")) if isinstance(item, dict)]
        normalized_renderers: list[dict[str, Any]] = []
        for renderer in renderers:
            renderer_id = str(renderer.get("id") or "")
            if not renderer_id:
                errors.append(f"module {module_id} has a renderer without id")
                continue
            row = dict(defaults)
            row.update(renderer)
            row["module_id"] = str(module_id)
            artifact_id = str(row.get("artifact") or "")
            renderer_ids.append(f"{module_id}.{renderer_id}")
            if artifact_id:
                artifact_refs.append(artifact_id)
            for key in ("artifact", "kind", "target", "privacy"):
                if not row.get(key):
                    errors.append(f"renderer {module_id}.{renderer_id} missing {key}")
            if known_artifacts and artifact_id and artifact_id not in known_artifacts:
                errors.append(f"renderer {module_id}.{renderer_id} references unknown artifact {artifact_id}")
            normalized_renderers.append(row)
        normalized[str(module_id)] = normalized_renderers
    duplicates = sorted({renderer_id for renderer_id in renderer_ids if renderer_ids.count(renderer_id) > 1})
    if duplicates:
        errors.append(f"duplicate renderer IDs: {', '.join(duplicates)}")
    declared_count = int(data.get("renderer_count") or 0)
    if declared_count and declared_count != len(renderer_ids):
        errors.append(f"renderer_count={declared_count} but renderers={len(renderer_ids)}")
    definitions = load_module_definitions()
    expected_modules = {
        str(item.get("id") or "")
        for item in as_list(definitions.get("modules"))
        if isinstance(item, dict) and item.get("id")
    } or set(MODULE_IDS)
    missing_modules = sorted(expected_modules - set(normalized.keys()))
    extra_modules = sorted(set(normalized.keys()) - expected_modules)
    data["modules"] = normalized
    data["renderer_count"] = len(renderer_ids)
    data["renderer_ids"] = sorted(renderer_ids)
    data["artifact_refs"] = sorted(set(artifact_refs))
    data["errors"] = errors
    data["missing_modules"] = missing_modules
    data["extra_modules"] = extra_modules
    data["ok"] = not errors and not missing_modules
    data["source"] = str(path.relative_to(ROOT))
    _MODULE_RENDERERS_CACHE = data
    return _MODULE_RENDERERS_CACHE


def load_module_implementation_contracts() -> dict[str, Any]:
    global _MODULE_IMPLEMENTATIONS_CACHE
    if _MODULE_IMPLEMENTATIONS_CACHE is not None:
        return _MODULE_IMPLEMENTATIONS_CACHE
    path = ROOT / "modules" / "implementations.yaml"
    if not path.exists():
        _MODULE_IMPLEMENTATIONS_CACHE = {
            "schema": "homenet.module_implementations.v1",
            "version": "",
            "implementation_count": 0,
            "modules": {},
            "errors": [f"{path.relative_to(ROOT)} is missing"],
        }
        return _MODULE_IMPLEMENTATIONS_CACHE
    data = load_yaml(path)
    if not isinstance(data, dict):
        _MODULE_IMPLEMENTATIONS_CACHE = {
            "schema": "homenet.module_implementations.v1",
            "version": "",
            "implementation_count": 0,
            "modules": {},
            "errors": [f"{path.relative_to(ROOT)} must contain a mapping"],
        }
        return _MODULE_IMPLEMENTATIONS_CACHE
    modules = data.get("modules") if isinstance(data.get("modules"), dict) else {}
    defaults = data.get("defaults") if isinstance(data.get("defaults"), dict) else {}
    renderer_contracts = load_module_renderer_contracts()
    known_renderer_ids = {
        str(item)
        for item in as_list(renderer_contracts.get("renderer_ids"))
        if str(item)
    }
    normalized: dict[str, list[dict[str, Any]]] = {}
    implementation_ids: list[str] = []
    errors = [str(item) for item in as_list(data.get("errors")) if item]

    for module_id, section in modules.items():
        if not isinstance(section, dict):
            errors.append(f"module {module_id} must contain a mapping")
            continue
        implementations = [item for item in as_list(section.get("implementations")) if isinstance(item, dict)]
        normalized_implementations: list[dict[str, Any]] = []
        for implementation in implementations:
            implementation_id = str(implementation.get("id") or "")
            if not implementation_id:
                errors.append(f"module {module_id} has an implementation without id")
                continue
            row = dict(defaults)
            row.update(implementation)
            row["module_id"] = str(module_id)
            full_id = f"{module_id}.{implementation_id}"
            implementation_ids.append(full_id)
            for key in ("implementation_surface", "implementation_status", "write_support", "adoption_target"):
                if not row.get(key):
                    errors.append(f"implementation {full_id} missing {key}")
            if known_renderer_ids and full_id not in known_renderer_ids:
                errors.append(f"implementation {full_id} has no matching renderer contract")
            if row.get("write_support") not in {"disabled", "review-only"}:
                errors.append(f"implementation {full_id} declares unsupported write_support={row.get('write_support')}")
            normalized_implementations.append(row)
        normalized[str(module_id)] = normalized_implementations

    duplicates = sorted({item for item in implementation_ids if implementation_ids.count(item) > 1})
    if duplicates:
        errors.append(f"duplicate implementation IDs: {', '.join(duplicates)}")
    declared_count = int(data.get("implementation_count") or 0)
    if declared_count and declared_count != len(implementation_ids):
        errors.append(f"implementation_count={declared_count} but implementations={len(implementation_ids)}")

    definitions = load_module_definitions()
    expected_modules = {
        str(item.get("id") or "")
        for item in as_list(definitions.get("modules"))
        if isinstance(item, dict) and item.get("id")
    } or set(MODULE_IDS)
    missing_modules = sorted(expected_modules - set(normalized.keys()))
    extra_modules = sorted(set(normalized.keys()) - expected_modules)
    missing_renderer_contracts = sorted(known_renderer_ids - set(implementation_ids))
    extra_implementations = sorted(set(implementation_ids) - known_renderer_ids)

    data["modules"] = normalized
    data["implementation_count"] = len(implementation_ids)
    data["implementation_ids"] = sorted(implementation_ids)
    data["errors"] = errors
    data["missing_modules"] = missing_modules
    data["extra_modules"] = extra_modules
    data["missing_renderer_contracts"] = missing_renderer_contracts
    data["extra_implementations"] = extra_implementations
    data["ok"] = not errors and not missing_modules and not missing_renderer_contracts and not extra_implementations
    data["source"] = str(path.relative_to(ROOT))
    _MODULE_IMPLEMENTATIONS_CACHE = data
    return _MODULE_IMPLEMENTATIONS_CACHE


def load_module_executor_contracts() -> dict[str, Any]:
    global _MODULE_EXECUTORS_CACHE
    if _MODULE_EXECUTORS_CACHE is not None:
        return _MODULE_EXECUTORS_CACHE
    path = ROOT / "modules" / "executors.yaml"
    if not path.exists():
        _MODULE_EXECUTORS_CACHE = {
            "schema": "homenet.module_executors.v1",
            "version": "",
            "writers": {},
            "executor_capabilities": {},
            "errors": [f"{path.relative_to(ROOT)} is missing"],
        }
        return _MODULE_EXECUTORS_CACHE
    data = load_yaml(path)
    if not isinstance(data, dict):
        _MODULE_EXECUTORS_CACHE = {
            "schema": "homenet.module_executors.v1",
            "version": "",
            "writers": {},
            "executor_capabilities": {},
            "errors": [f"{path.relative_to(ROOT)} must contain a mapping"],
        }
        return _MODULE_EXECUTORS_CACHE
    writers = data.get("writers") if isinstance(data.get("writers"), dict) else {}
    capabilities = data.get("executor_capabilities") if isinstance(data.get("executor_capabilities"), dict) else {}
    readiness_gates = data.get("readiness_gates") if isinstance(data.get("readiness_gates"), dict) else {}
    errors = [str(item) for item in as_list(data.get("errors")) if item]
    for writer_id, writer in writers.items():
        if not isinstance(writer, dict):
            errors.append(f"writer {writer_id} must contain a mapping")
            continue
        for key in ("owner", "source_tool", "write_surface", "boundary"):
            if not writer.get(key):
                errors.append(f"writer {writer_id} missing {key}")
    for writer_id, capability in capabilities.items():
        if not isinstance(capability, dict):
            errors.append(f"executor capability {writer_id} must contain a mapping")
            continue
        for key in ("implementation_status", "supports_dry_run", "supports_write", "supported_operations", "disabled_reason", "implementation_required"):
            if key not in capability:
                errors.append(f"executor capability {writer_id} missing {key}")
    missing_capabilities = sorted(set(writers.keys()) - set(capabilities.keys()))
    extra_capabilities = sorted(set(capabilities.keys()) - set(writers.keys()))
    if missing_capabilities:
        errors.append(f"writers missing executor capabilities: {', '.join(missing_capabilities)}")
    if extra_capabilities:
        errors.append(f"executor capabilities without writers: {', '.join(extra_capabilities)}")
    missing_readiness = sorted(set(writers.keys()) - set(readiness_gates.keys()))
    extra_readiness = sorted(set(readiness_gates.keys()) - set(writers.keys()))
    if missing_readiness:
        errors.append(f"writers missing readiness gates: {', '.join(missing_readiness)}")
    if extra_readiness:
        errors.append(f"readiness gates without writers: {', '.join(extra_readiness)}")
    for writer_id, gates in readiness_gates.items():
        if not isinstance(gates, dict):
            errors.append(f"readiness gates {writer_id} must contain a mapping")
            continue
        if not as_list(gates.get("required")):
            errors.append(f"readiness gates {writer_id} missing required")
        if not gates.get("promotion_rule"):
            errors.append(f"readiness gates {writer_id} missing promotion_rule")
    data["writers"] = writers
    data["executor_capabilities"] = capabilities
    data["readiness_gates"] = readiness_gates
    data["writer_count"] = len(writers)
    data["executor_capability_count"] = len(capabilities)
    data["readiness_gate_count"] = len(readiness_gates)
    data["errors"] = errors
    data["ok"] = not errors
    data["source"] = str(path.relative_to(ROOT))
    _MODULE_EXECUTORS_CACHE = data
    return _MODULE_EXECUTORS_CACHE


def load_module_backup_contracts() -> dict[str, Any]:
    global _MODULE_BACKUPS_CACHE
    if _MODULE_BACKUPS_CACHE is not None:
        return _MODULE_BACKUPS_CACHE
    path = ROOT / "modules" / "backups.yaml"
    if not path.exists():
        _MODULE_BACKUPS_CACHE = {
            "schema": "homenet.module_backups.v1",
            "version": "",
            "method_capabilities": {},
            "errors": [f"{path.relative_to(ROOT)} is missing"],
        }
        return _MODULE_BACKUPS_CACHE
    data = load_yaml(path)
    if not isinstance(data, dict):
        _MODULE_BACKUPS_CACHE = {
            "schema": "homenet.module_backups.v1",
            "version": "",
            "method_capabilities": {},
            "errors": [f"{path.relative_to(ROOT)} must contain a mapping"],
        }
        return _MODULE_BACKUPS_CACHE
    capabilities = data.get("method_capabilities") if isinstance(data.get("method_capabilities"), dict) else {}
    errors = [str(item) for item in as_list(data.get("errors")) if item]
    for method, capability in capabilities.items():
        if not isinstance(capability, dict):
            errors.append(f"backup method {method} must contain a mapping")
            continue
        for key in ("owner", "implementation_status", "supports_plan", "supports_capture", "supports_restore", "supports_verify", "disabled_reason", "implementation_required"):
            if key not in capability:
                errors.append(f"backup method {method} missing {key}")
    data["method_capabilities"] = capabilities
    data["method_count"] = len(capabilities)
    data["errors"] = errors
    data["ok"] = not errors
    data["source"] = str(path.relative_to(ROOT))
    _MODULE_BACKUPS_CACHE = data
    return _MODULE_BACKUPS_CACHE
