# Versioning Boundary

This directory is versioned as the HomeNet operator repository.

Use the CLI version surface to confirm the current checkout, instance profile,
and sibling project ownership:

```sh
./homenet version --instance instances/my-home
./homenet workspace --instance instances/my-home
./homenet progress --instance instances/my-home
./homenet gates --instance instances/my-home
```

The current reusable core version is `1.0.0`. Treat this as the first stable
public HomeNet core release plus one private deployment instance, not as a
publishable copy of the whole live workspace.

The root repository owns the reusable orchestration layer:

- `homenet` and `tools/homenet.py`
- `README.md`
- `docs/`
- `schemas/`
- `instances/example-*`
- sanitized instance declarations under `instances/`
- reusable HomeNet modules plus maintenance/source-tool helper scripts under `maintenance/`
- HomeNet Ops source under `apps/ops/`, integration contracts, metadata, service directory, and generated review surfaces

The root repository owns HomeNet Ops source under `apps/ops/`. The root does not own live runtime state, local secrets, or private deployment output. These paths stay untracked:

- `.env`, `.agents/`, `.codex/`
- `adguard/conf/`, `adguard/work/`
- `backups/`
- `caddy/config/`, `caddy/data/`
- `cloudflared/`
- `ddns-go/`
- `wg-easy/data/`
- `maintenance/state/`, `maintenance/backups/`
- Mihomo runtime config, cache, proxies, downloaded rule databases, and UI assets

## Workspace Projects

`apps/ops/` is part of the HomeNet root repository. `sub/` is a separate private project in the same workspace and keeps its own `.git` directory.

Use this split so the HomeNet root can be reviewed, backed up, and published with its simple Ops UI without accidentally absorbing private Worker build output, Wrangler state, or local runtime data.

The `homenet version` report should show the root repository as the HomeNet
core including `apps/ops/`, and `sub/` as a separate workspace project. A dirty
state in the private project does not imply the root should be committed together with it.

The `homenet workspace` report is the review view for this mixed directory. It
lists each boundary, whether the root repository tracks it, which directory to
commit from, and whether it can be part of a public HomeNet release. Use it
before handing the workspace to another operator or AI assistant.

When changing the private project, commit it from its own directory:

```sh
git -C sub status
```

## Before Commit

Run these checks from the root before committing:

```sh
./homenet privacy --scope public
./homenet privacy --scope all --instance instances/my-home
./homenet deploy --instance instances/my-home --force --check-idempotent
./homenet check --instance instances/my-home
./homenet package --instance instances/my-home --output-dir /tmp/homenet-public --force
./homenet package-check --dir /tmp/homenet-public
./homenet package-smoke --dir /tmp/homenet-public
./homenet workspace --instance instances/my-home
```

The privacy commands must not print matched secret values. If they report a finding, fix the file or keep it untracked before committing.
