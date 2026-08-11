# HomeNet Public Package

This package is the reusable HomeNet public core. It is not a copy of a
live home deployment.

Use it to create a private deployment instance for one home, then keep that
instance's secrets, runtime data, service databases, subscriptions, certificates,
and local overrides outside the public package.

## What Is Included

- `homenet` and `tools/homenet.py`: read-only CLI, checks, review surfaces, and package tools.
- `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`, and `PUBLISHING.md`: public
  use rights, contribution boundaries, sensitive-data reporting rules, and
  public release review.
- `schemas/`: instance schemas for site, devices, and services.
- `modules/`: reusable module catalog, artifact contracts, renderer contracts, executor contracts, and backup contracts.
- `instances/example-openwrt-pi/`: example for OpenWrt plus Pi, mini PC, NAS, or another server runtime.
- `instances/example-openwrt-only/`: example for router-only deployments.
- `apps/ops/`: HomeNet Ops source, the simple daily status, service entry, topology, and troubleshooting surface.
- `templates/compose/`: public Docker Compose starting point for server-runtime profiles.
- `maintenance/`: maintenance/source-tool helper scripts kept as explicit files instead of hidden one-off commands.
- `docs/`: operator path and product design notes.

## What Is Not Included

- Real home instances such as `instances/<private-home>/`.
- Filled `.env` files, Wi-Fi passwords, proxy subscriptions, API tokens, private keys, cookies, and sessions.
- Runtime directories such as `adguard/`, `mihomo/`, `wg-easy/`, `caddy/`, `cloudflared/`, `ddns-go/`, and `backups/`.
- Private subscription Worker source such as `sub/`.

## First Deployment Path

Start with the interactive initializer:

```sh
./homenet init
```

It asks for the instance name, profile, domain placeholder, OpenWrt IP, whether
there is a Pi/server runtime, Room AP, Maintenance Wi-Fi, Remote Access, and Smart Home.
It is idempotent: the same answers produce the same instance files; an existing
matching directory is reported as unchanged, and differing contents are not
overwritten unless confirmed or `--force` is used.

For non-interactive use:

```sh
./homenet init --yes --name my-home --profile openwrt-pi
./homenet deploy --instance instances/my-home --output-dir /tmp/homenet-deploy --force --check-idempotent
./homenet check --instance instances/my-home
```

`deploy --check-idempotent` and `check` are the main deployment checkpoints.
They show the source-tool sequence, write the minimal deployment files, and
prove repeat generation is stable without changing live network state.
`status --live` and `doctor --live` are the first troubleshooting layer after
deployment. Deeper module, release gate, apply, backup, and proof commands are
advanced references, not the normal usage path.

For the exact useful/advanced/non-goal split, read `docs/function-boundary.md`.

For the full deployment and existing-home adoption path, read
`docs/deployment-and-adoption.md` before changing source tools.
For the smallest deployable shape and non-goals, read
`docs/minimal-deployment.md`.
For per-source-tool backup, setup, verify, and rollback steps, read
`docs/source-tool-runbook.md`.

For an OpenWrt-only deployment, use:

```sh
./homenet init --profile openwrt-only
```

For a higher-capacity always-on host, use:

```sh
./homenet init --profile openwrt-mini-pc
```

## Server Runtime Template

For `openwrt-pi` and `openwrt-mini-pc`, copy the compose template into a private
deployment directory and fill local secrets there:

```sh
cp templates/compose/docker-compose.yml ./docker-compose.yml
cp templates/compose/env.example ./.env
```

Do not commit the filled `.env`, service databases, certificates, WireGuard
data, Cloudflare credentials, or proxy subscriptions.

## Review Before Live Changes

HomeNet is review-first. Generated outputs explain what should exist and
what a future apply would need; live writes remain source-tool controlled until
guarded apply is implemented and verified.

```sh
./homenet deploy --instance instances/my-home --output-dir /tmp/homenet-deploy --force --check-idempotent
./homenet check --instance instances/my-home
./homenet status --instance instances/my-home --live
```

Use OpenWrt/LuCI/UCI, Docker/systemd, Cloudflare, Kuma, Home Assistant, or other
source tools for live changes until the relevant module executor is explicitly
write-enabled.

Advanced review commands such as `deploy --dry-run`, `apply --dry-run`,
`rollback`, `bundle`, `gates`, and `evidence` are available when preparing
automation or auditing a larger change. They are not required for the normal
first deployment path.

## Package Verification

When this package is exported from a mixed private workspace, verify that the
public package is complete and that private/runtime paths were not copied:

```sh
./homenet package-check --dir /path/to/homenet-public
./homenet package-smoke --dir /path/to/homenet-public
./homenet check --instance instances/example-openwrt-pi
./homenet check --instance instances/example-openwrt-only
```

The package check validates paths and `PUBLIC_PACKAGE_MANIFEST.json` shape. It
does not read package file contents except the manifest and does not access live
network infrastructure.

Inside an exported package without `.git`, `homenet package` and release checks use
`PUBLIC_PACKAGE_MANIFEST.json` as the package file list.

The package includes `.github/workflows/ci.yml` for public repositories. It
runs public privacy, example CI, package manifest, package check, and package
smoke without requiring repository secrets.

`package-smoke` runs the package check plus read-only package and example CI
commands inside the exported directory. It confirms that the package can operate
away from the original private workspace, but it is heavier than
`package-check`.

Maintainers publishing an official public repository may additionally use
`release-candidate`, `publish-check`, `repo-init`, `publish-audit`,
`repo-publish`, and `repo-plan`. These are release tools, not deployment tools.
