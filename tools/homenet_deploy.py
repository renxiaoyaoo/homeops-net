from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Callable

from tools.homenet_check import as_list


def build_deploy_plan(state: dict[str, Any], instance: Path, deps: dict[str, Callable[..., Any]]) -> dict[str, Any]:
    plan = deps["build_plan"](state, instance)
    inputs = deps["build_inputs_checklist"](state, instance)
    secrets = deps["build_secrets_contract"](state, instance)
    preflight = deps["build_preflight"](state, instance)
    readiness = deps["build_readiness"](state, instance)
    rollback = deps["build_rollback_contract"](state, instance)
    evidence = deps["build_evidence_plan"](state, instance)
    artifacts = deps["build_artifact_manifest"](deps["build_metadata"](state, instance))
    apply_plan = deps["build_apply_plan"](state, instance)
    config_plan = deps["build_config_plan"](deps["build_metadata"](state, instance), instance)
    config_summary = config_plan.get("summary", {}) if isinstance(config_plan.get("summary"), dict) else {}
    apply_summary = apply_plan.get("summary", {}) if isinstance(apply_plan.get("summary"), dict) else {}
    rollback_summary = rollback.get("summary", {}) if isinstance(rollback.get("summary"), dict) else {}
    backup_contract = {
        "backup_required_artifacts": rollback_summary.get("backup_required_artifacts", 0),
        "backup_plan_items": len(as_list(rollback.get("backup_plan"))),
        "apply_backup_plan_items": len(as_list(apply_plan.get("backup_plan"))),
        "modules_with_backup_plan": sum(1 for module in rollback.get("modules", []) if isinstance(module, dict) and module.get("backup_plan")),
        "execute_by_default": any(
            bool(item.get("execute_by_default"))
            for item in as_list(apply_plan.get("backup_plan"))
            if isinstance(item, dict)
        ),
    }

    blockers: list[dict[str, Any]] = []
    if inputs.get("summary", {}).get("required_missing"):
        blockers.append({
            "source": "inputs",
            "id": "required-inputs-missing",
            "detail": f"{inputs.get('summary', {}).get('required_missing')} required deployment input(s) are missing.",
        })
    for item in preflight.get("blockers", []):
        if isinstance(item, dict):
            blockers.append({
                "source": "preflight",
                "id": item.get("id") or "preflight",
                "detail": item.get("detail") or "",
            })
    for item in readiness.get("apply_blockers", []):
        if isinstance(item, dict):
            blockers.append({
                "source": "readiness",
                "id": item.get("id") or "readiness",
                "detail": item.get("detail") or "",
            })
    blockers.append({
        "source": "deploy",
        "id": "write-side-disabled",
        "detail": "This build only emits a deployment dry-run. It does not write OpenWrt, Docker, systemd, Kuma, Cloudflare, or service configs.",
    })

    steps = [
        {
            "order": 1,
            "phase": "select-profile",
            "status": "ready",
            "command": "./homenet profiles",
            "detail": f"Selected profile is {plan.get('profile')}.",
        },
        {
            "order": 2,
            "phase": "scaffold-or-edit-instance",
            "status": "ready" if not inputs.get("summary", {}).get("required_missing") else "blocked",
            "command": "./homenet inputs --instance <instance>",
            "detail": "Confirm site.yaml, devices.yaml, services.yaml, runtime targets, networks, Wi-Fi, modules, and secret names.",
        },
        {
            "order": 3,
            "phase": "provide-secrets",
            "status": "operator-action",
            "command": "./homenet secrets --instance <instance>",
            "detail": f"Provide {secrets.get('required_count', 0)} required secret value(s) outside instance files and git.",
        },
        {
            "order": 4,
            "phase": "operator-preflight",
            "status": "ready" if not preflight.get("blockers") else "blocked",
            "command": "./homenet preflight --instance <instance>",
            "detail": "Check local command dependencies and secret name presence on the machine that will operate deployment.",
        },
        {
            "order": 5,
            "phase": "review-bundle",
            "status": "ready",
            "command": "./homenet bundle --instance <instance> --output <dir>",
            "detail": "Review generated profiles, modules, inputs, secrets, readiness, rollback, evidence, artifacts, config plan, and docs together.",
        },
        {
            "order": 6,
            "phase": "backup-contract",
            "status": "review-required",
            "command": "./homenet rollback --instance <instance>",
            "detail": f"Review rollback sources and {backup_contract.get('backup_plan_items', 0)} backup capture/restore/verify plan(s).",
        },
        {
            "order": 7,
            "phase": "render-review",
            "status": "review-required",
            "command": "./homenet generate --instance <instance> --dry-run",
            "detail": f"Review {config_summary.get('fragments', 0)} config review artifact(s); rendered review artifacts {config_summary.get('rendered_review_artifacts', 0)}, deployable currently {config_summary.get('deployable_fragments', 0)}.",
        },
        {
            "order": 8,
            "phase": "apply-contract",
            "status": "disabled",
            "command": "./homenet apply --instance <instance> --dry-run",
            "detail": "Write-side apply remains disabled; inspect artifact order, blockers, and verification commands only.",
        },
        {
            "order": 9,
            "phase": "live-verify",
            "status": "ready-after-operator-review",
            "command": "./homenet verify --instance <instance> --live",
            "detail": f"Read live evidence plan with {evidence.get('summary', {}).get('checks', 0)} check(s) after any manual or future apply work.",
        },
    ]
    by_status: dict[str, int] = {}
    for step in steps:
        status = str(step.get("status") or "")
        by_status[status] = by_status.get(status, 0) + 1

    return {
        "schema": "homenet.deploy_plan.v1",
        "instance": plan.get("instance") or {},
        "instance_path": str(instance),
        "profile": plan.get("profile"),
        "read_only": True,
        "dry_run": True,
        "writes_files": False,
        "writes_live_config": False,
        "summary": {
            "steps": len(steps),
            "blockers": len(blockers),
            "artifacts": artifacts.get("artifact_count", 0),
            "required_inputs_missing": inputs.get("summary", {}).get("required_missing", 0),
            "required_secrets": secrets.get("required_count", 0),
            "preflight_blockers": preflight.get("summary", {}).get("blockers", 0),
            "apply_blockers": readiness.get("summary", {}).get("apply_blockers", 0),
            "apply_plan_artifacts": apply_summary.get("artifacts", 0),
            "backup_plan_items": backup_contract.get("backup_plan_items", 0),
            "rendered_review_artifacts": config_summary.get("rendered_review_artifacts", 0),
            "review_fragments": config_summary.get("review_fragments", 0),
        },
        "by_status": dict(sorted(by_status.items())),
        "steps": steps,
        "blockers": blockers,
        "inputs_summary": inputs.get("summary", {}),
        "preflight_summary": preflight.get("summary", {}),
        "readiness_summary": readiness.get("summary", {}),
        "rollback_summary": rollback_summary,
        "apply_summary": apply_summary,
        "config_summary": config_summary,
        "backup_contract": backup_contract,
        "next": [
            "Treat this deploy plan as the end-to-end checklist.",
            "Use apply --dry-run for artifact order and write-side contract details.",
            "Do not enable write-side apply until review artifacts, backups, secret scope, and live verification gates are reviewed.",
        ],
        "privacy": {
            "secrets_included": False,
            "secret_values_checked": False,
            "live_state_read": False,
            "note": "Deploy dry-run lists phases, commands, and blocker counts only; it does not read or print secret values or mutate infrastructure.",
        },
    }




def print_deploy_plan_markdown(deploy: dict[str, Any]) -> None:
    instance = deploy.get("instance", {})
    name = instance.get("display_name") or instance.get("name") or Path(str(deploy.get("instance_path", "instance"))).name
    print(f"# Deploy Dry Run - {name}")
    print()
    print(f"- schema: `{deploy.get('schema')}`")
    print(f"- profile: `{deploy.get('profile')}`")
    print(f"- read only: {deploy.get('read_only')}")
    print(f"- dry run: {deploy.get('dry_run')}")
    print(f"- writes files: {deploy.get('writes_files')}")
    print(f"- writes live config: {deploy.get('writes_live_config')}")
    print()
    print("## Summary")
    print()
    for key, value in deploy.get("summary", {}).items():
        print(f"- {key}: {value}")
    print()
    if deploy.get("config_summary"):
        print("## Config Review")
        print()
        for key in ["fragments", "rendered_review_artifacts", "review_fragments", "deployable_fragments", "promotion_gates", "promotion_blockers"]:
            if key in deploy.get("config_summary", {}):
                print(f"- {key}: {deploy.get('config_summary', {}).get(key)}")
        print()
    if deploy.get("backup_contract"):
        print("## Backup Contract")
        print()
        for key, value in deploy.get("backup_contract", {}).items():
            print(f"- {key}: {value}")
        print()
    print("## Steps")
    print()
    print("| Order | Phase | Status | Command | Detail |")
    print("| --- | --- | --- | --- | --- |")
    for step in deploy.get("steps", []):
        if isinstance(step, dict):
            print(
                f"| {step.get('order', '')} | {step.get('phase', '')} | {step.get('status', '')} | "
                f"`{step.get('command', '')}` | {step.get('detail', '')} |"
            )
    print()
    if deploy.get("blockers"):
        print("## Blockers")
        print()
        for item in deploy.get("blockers", []):
            if isinstance(item, dict):
                print(f"- {item.get('source')}/{item.get('id')}: {item.get('detail')}")
        print()
    print("## Next")
    print()
    for item in deploy.get("next", []):
        print(f"- {item}")
    print()


def snapshot_directory(path: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    if not path.exists():
        return snapshot
    for file_path in sorted(item for item in path.rglob("*") if item.is_file()):
        rel = file_path.relative_to(path).as_posix()
        snapshot[rel] = file_path.read_text(encoding="utf-8")
    return snapshot


def check_deploy_kit_idempotency(build_deploy_kit: Callable[..., dict[str, Any]], state: dict[str, Any], instance: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="homenet-deploy-") as tmp:
        base = Path(tmp)
        first_dir = base / "first"
        second_dir = base / "second"
        first = build_deploy_kit(state, instance, first_dir, force=True)
        second = build_deploy_kit(state, instance, second_dir, force=True)
        first_snapshot = snapshot_directory(first_dir)
        second_snapshot = snapshot_directory(second_dir)
        first_files = set(first_snapshot)
        second_files = set(second_snapshot)
        changed = sorted(
            name
            for name in first_files & second_files
            if first_snapshot.get(name) != second_snapshot.get(name)
        )
        missing = sorted(first_files - second_files)
        extra = sorted(second_files - first_files)
        ok = bool(first.get("ok")) and bool(second.get("ok")) and not changed and not missing and not extra
        return {
            "schema": "homenet.deploy_idempotency.v1",
            "ok": ok,
            "writes_live_config": False,
            "runs": 2,
            "files_checked": len(first_files | second_files),
            "changed": changed,
            "missing": missing,
            "extra": extra,
            "errors": as_list(first.get("errors")) + as_list(second.get("errors")),
        }


def print_deploy_kit_markdown(kit: dict[str, Any]) -> None:
    print("# HomeNet Deploy")
    print()
    print(f"- ok: {kit.get('ok')}")
    print(f"- instance: `{kit.get('instance')}`")
    print(f"- profile: `{kit.get('profile')}`")
    print(f"- output dir: `{kit.get('output_dir')}`")
    print(f"- writes files: {kit.get('writes_files')}")
    print(f"- writes live config: {kit.get('writes_live_config')}")
    print()
    print("## Minimal Steps")
    print()
    for step in as_list(kit.get("steps")):
        if isinstance(step, dict):
            print(f"{step.get('order')}. **{step.get('name')}**: {step.get('do')}")
            print(f"   - check: `{step.get('check')}`")
    print()
    print("## Files")
    print()
    for item in as_list(kit.get("files")):
        print(f"- `{item}`")
    idempotency = kit.get("idempotency")
    if isinstance(idempotency, dict):
        print()
        print("## Idempotency")
        print()
        print(f"- ok: {idempotency.get('ok')}")
        print(f"- runs: {idempotency.get('runs')}")
        print(f"- files checked: {idempotency.get('files_checked')}")
        print(f"- writes live config: {idempotency.get('writes_live_config')}")
        if idempotency.get("changed") or idempotency.get("missing") or idempotency.get("extra"):
            print(f"- changed: {', '.join(as_list(idempotency.get('changed'))) or '-'}")
            print(f"- missing: {', '.join(as_list(idempotency.get('missing'))) or '-'}")
            print(f"- extra: {', '.join(as_list(idempotency.get('extra'))) or '-'}")
    if kit.get("errors"):
        print()
        print("## Errors")
        print()
        for item in as_list(kit.get("errors")):
            if isinstance(item, dict):
                print(f"- {item.get('id')}: {item.get('detail')}")
    print()
