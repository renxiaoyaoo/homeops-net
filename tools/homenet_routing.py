from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any


ROUTING_PERMANENT_RULE_TARGETS = {
    "DIRECT": "my-direct.yaml",
    "PROXY": "my-proxy.yaml",
    "PROXY-JAPAN": "my-japan.yaml",
    "AI-NODES": "my-ai.yaml",
    "IPV6-NODES": "my-ipv6.yaml",
}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_ops_routing_store(store: Path) -> dict[str, Any]:
    try:
        data = json.loads(store.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "error": f"{store} is not valid JSON: {exc}",
            "entries": [],
            "permanent_candidates": [],
        }
    if not isinstance(data, dict):
        return {"ok": False, "error": f"{store} root is not an object", "entries": [], "permanent_candidates": []}
    entries = data.get("entries") if isinstance(data.get("entries"), list) else []
    candidates = data.get("permanent_candidates") if isinstance(data.get("permanent_candidates"), list) else []
    return {
        "ok": True,
        "schema": data.get("schema") or "",
        "updated_at": data.get("updated_at"),
        "entries": [item for item in entries if isinstance(item, dict)],
        "permanent_candidates": [item for item in candidates if isinstance(item, dict)],
    }


def payload_rules_from_text(text: str) -> list[str]:
    rules: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^\s*-\s*(.+?)\s*$", line)
        if match:
            rules.append(match.group(1).strip())
    return rules


def append_payload_rules(path: Path, rules: list[str], *, dry_run: bool) -> dict[str, Any]:
    existing_text = path.read_text(encoding="utf-8") if path.exists() else "payload: []\n"
    existing_rules = payload_rules_from_text(existing_text)
    existing_set = set(existing_rules)
    added = [rule for rule in rules if rule and rule not in existing_set]
    if dry_run or not added:
        return {"path": str(path), "existing": len(existing_rules), "added": added, "changed": bool(added)}

    if existing_text.strip() == "payload: []":
        new_text = "payload:\n" + "".join(f"  - {rule}\n" for rule in added)
    else:
        body = existing_text.rstrip() + "\n"
        new_text = body + "".join(f"  - {rule}\n" for rule in added)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new_text, encoding="utf-8")
    return {"path": str(path), "existing": len(existing_rules), "added": added, "changed": True}


def write_ops_routing_store(store: Path, original: dict[str, Any], candidates: list[dict[str, Any]]) -> None:
    payload = {
        "schema": original.get("schema") or "homenet.routing-rules.v1",
        "updated_at": time.time(),
        "entries": as_list(original.get("entries")),
        "permanent_candidates": candidates,
    }
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_routing_status_report(store: Path) -> dict[str, Any]:
    data = load_ops_routing_store(store)
    return {
        "schema": "homenet.routing-status.v1",
        "ok": bool(data.get("ok")),
        "store": str(store),
        "error": data.get("error", ""),
        "temporary_entries": as_list(data.get("entries")),
        "permanent_candidates": as_list(data.get("permanent_candidates")),
        "summary": {
            "temporary_entries": len(as_list(data.get("entries"))),
            "permanent_candidates": len(as_list(data.get("permanent_candidates"))),
        },
    }


def build_routing_commit_report(
    *,
    store: Path,
    source_root: Path,
    dry_run: bool,
    confirm_permanent: bool,
) -> dict[str, Any]:
    data = load_ops_routing_store(store)
    candidates = as_list(data.get("permanent_candidates"))
    report: dict[str, Any] = {
        "schema": "homenet.routing-commit.v1",
        "ok": False,
        "store": str(store),
        "source_root": str(source_root),
        "dry_run": dry_run,
        "writes_files": False,
        "writes_live_config": False,
        "requires_confirmation": True,
        "confirmed": confirm_permanent,
        "summary": {
            "pending": len(candidates),
            "committed": 0,
            "skipped": 0,
            "files_changed": 0,
        },
        "files": [],
        "errors": [],
    }
    if not data.get("ok"):
        report["errors"].append(data.get("error") or "routing store unreadable")
        return report
    if not candidates:
        report["ok"] = True
        return report
    if not dry_run and not confirm_permanent:
        report["errors"].append("refusing to write permanent rules without --confirm-permanent")
        return report

    rules_dir = source_root / "rules"
    by_file: dict[str, list[str]] = {}
    committed_ids: set[str] = set()
    for item in candidates:
        policy = str(item.get("policy") or "").upper()
        rule = str(item.get("rule") or "").strip()
        candidate_id = str(item.get("id") or "")
        target_file = ROUTING_PERMANENT_RULE_TARGETS.get(policy)
        if not target_file or not rule:
            report["summary"]["skipped"] += 1
            report["errors"].append(f"unsupported pending rule: policy={policy or '?'} value={item.get('value') or '?'}")
            continue
        by_file.setdefault(target_file, []).append(rule)
        committed_ids.add(candidate_id)

    for file_name, rules in sorted(by_file.items()):
        result = append_payload_rules(rules_dir / file_name, rules, dry_run=dry_run)
        report["files"].append(result)
        if result.get("changed"):
            report["summary"]["files_changed"] += 1
        report["summary"]["committed"] += len(result.get("added") or [])

    if not dry_run and not report["errors"]:
        remaining = [
            item for item in candidates
            if str(item.get("id") or "") not in committed_ids
        ]
        write_ops_routing_store(store, data, remaining)
        report["writes_files"] = True

    report["ok"] = not bool(report["errors"])
    return report


def print_routing_status_markdown(report: dict[str, Any]) -> None:
    print("# HomeNet Routing")
    print()
    print(f"- store: `{report.get('store')}`")
    print(f"- ok: {report.get('ok')}")
    if report.get("error"):
        print(f"- error: {report.get('error')}")
    summary = report.get("summary", {}) if isinstance(report.get("summary"), dict) else {}
    print(f"- temporary entries: {summary.get('temporary_entries', 0)}")
    print(f"- permanent pending: {summary.get('permanent_candidates', 0)}")
    print()
    print("## Permanent Pending")
    print()
    for item in as_list(report.get("permanent_candidates")):
        print(f"- {item.get('value')} -> {item.get('policy')} (`{item.get('rule')}`)")
    if not as_list(report.get("permanent_candidates")):
        print("- none")


def print_routing_commit_markdown(report: dict[str, Any]) -> None:
    print("# HomeNet Routing Commit")
    print()
    print(f"- ok: {report.get('ok')}")
    print(f"- dry run: {report.get('dry_run')}")
    print(f"- writes files: {report.get('writes_files')}")
    print(f"- writes live config: {report.get('writes_live_config')}")
    summary = report.get("summary", {}) if isinstance(report.get("summary"), dict) else {}
    print(f"- pending: {summary.get('pending', 0)}")
    print(f"- committed rules: {summary.get('committed', 0)}")
    print(f"- files changed: {summary.get('files_changed', 0)}")
    if report.get("errors"):
        print()
        print("## Errors")
        print()
        for error in as_list(report.get("errors")):
            print(f"- {error}")
    print()
    print("## Files")
    print()
    for item in as_list(report.get("files")):
        added = ", ".join(f"`{rule}`" for rule in as_list(item.get("added")))
        print(f"- `{item.get('path')}`: {'add ' + added if added else 'no change'}")
    if not as_list(report.get("files")):
        print("- none")


def command_routing(args: argparse.Namespace) -> int:
    store = Path(args.store).resolve()
    if args.routing_command == "status":
        report = build_routing_status_report(store)
        if args.format == "json":
            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print_routing_status_markdown(report)
        return 0 if report.get("ok") else 2
    if args.routing_command == "commit":
        report = build_routing_commit_report(
            store=store,
            source_root=Path(args.source_root).resolve(),
            dry_run=bool(args.dry_run) or not bool(args.confirm_permanent),
            confirm_permanent=bool(args.confirm_permanent),
        )
        if args.format == "json":
            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print_routing_commit_markdown(report)
        return 0 if report.get("ok") else 2
    print("unknown routing command", file=sys.stderr)
    return 2
