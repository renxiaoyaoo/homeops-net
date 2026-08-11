# Deployment And Adoption

HomeNet is a deployable home network operating model first. Ops and status
views are supporting surfaces for troubleshooting; they are not the source of
truth and they are not the first thing to build.

## What Gets Deployed

A deployment has three layers:

1. Instance files: `site.yaml`, `devices.yaml`, and `services.yaml`.
2. Source tools: OpenWrt, Docker/systemd, AdGuard, Mihomo, Cloudflare, Kuma,
   WireGuard, Home Assistant, and device-native settings.
3. Observation: HomeNet CLI/Ops, Kuma history, service inventory, topology,
   and incident checks.

The instance files describe the intended network. Source tools own live state.
Observation checks whether the live state still matches the intent.

## New Home Path

Start with the smallest path that creates a working private instance:

```sh
./homenet init --name my-home --profile openwrt-pi
./homenet deploy --instance instances/my-home --force --check-idempotent
./homenet check --instance instances/my-home
```

Choose another profile only when the hardware shape is different:

- `openwrt-pi`: normal OpenWrt gateway plus Pi, NAS, mini PC, or another
  always-on Linux host.
- `openwrt-mini-pc`: same model with more capacity for services.
- `openwrt-only`: router-only fallback with lighter observability and runtime.

## Existing Home Adoption

Do not reinstall a working home network first. Model it, review it, then move
one source tool at a time.

```sh
./homenet init --name my-home --profile openwrt-pi
./homenet deploy --instance instances/my-home --force --check-idempotent
./homenet check --instance instances/my-home
```

Adoption order:

1. Gateway: record WAN, LAN, VLANs, DHCP, static leases, firewall, Wi-Fi, Maintenance
   Wi-Fi, and Room AP intent.
2. DNS/Proxy: record AdGuard and Mihomo placement, ports, DNS forwarding,
   transparent proxy policy, and explicit proxy endpoints.
3. Server runtime: record Docker/systemd services and expected ports.
4. Remote access: record Cloudflare Tunnel, Access apps, DNS records, DDNS,
   WireGuard peers, and IPv6 direct entries.
5. Observability: record Kuma monitors, HomeNet Ops, status pages, and
   notification responsibilities.
6. Smart home and optional modules: record Home Assistant, MQTT, Zigbee2MQTT,
   cameras, and device-specific quirks.

`deploy --check-idempotent` and `check` are the default checkpoints for this
order. They tell the operator which source tool is next, produce the minimal
deployment review, and prove repeated generation is stable. Use `bootstrap`
only when you need the expanded first-install checklist; use `deploy --dry-run`
only when you need the full review contract.

For each layer, apply changes in the owning source tool and verify before
moving to the next layer:

```sh
./homenet check --instance instances/my-home --live
./homenet doctor --instance instances/my-home --live
./homenet status --instance instances/my-home --live
```

## Server Runtime Template

For `openwrt-pi` and `openwrt-mini-pc`, let `deploy` generate the private
server-runtime draft first:

```sh
./homenet deploy --instance instances/my-home --force --check-idempotent
cd /tmp/homenet-deploy
cp runtime/env.example runtime/.env
runtime/check.sh
```

Fill local secrets in `runtime/.env`, then start services from the owning
server-runtime host when the config validates.

Do not commit filled `.env` files, service databases, certificates, WireGuard
data, Cloudflare credentials, proxy subscriptions, or backups.

## Daily Use

Daily entry:

```sh
./homenet status --instance instances/my-home
./homenet topology --instance instances/my-home
./homenet runbook --instance instances/my-home
```

When the network is slow or unstable:

```sh
./homenet incident --instance instances/my-home --live
./homenet status --instance instances/my-home --live
./homenet doctor --instance instances/my-home --live
```

Use Ops to localize the failure domain. Use the source tool to change
configuration.

Per-source-tool backup, setup, verification, and rollback steps are in
`docs/source-tool-runbook.md`.

## Cutover Rules

- Do not batch unrelated changes.
- Do not reset OpenWrt or rebuild services just because one check is red.
- Keep the old working source-tool config until the new intent is verified.
- Keep a low-dependency rescue path before changing DNS or proxy behavior.
- After every source-tool change, run a live verification command and record
  what changed.

## What Is Not Automated Yet

HomeNet currently produces deployment plans, review bundles, generated
review artifacts, source-tool sequences, rollback contracts, and live evidence
checks. It does not yet perform guarded live apply. Real changes still happen in
OpenWrt, Docker/systemd, Cloudflare, Kuma, Home Assistant, and the related
source tools.
