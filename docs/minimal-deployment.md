# Minimal Deployment Shape

HomeNet is a small home-network deployment template, not a replacement for
OpenWrt, Docker, Mihomo, AdGuard, Cloudflare, WireGuard, Kuma, or Home
Assistant.

The minimal shape is:

1. `site.yaml`: networks, Wi-Fi names, runtime hosts, remote entries, and enabled
   modules.
2. `devices.yaml`: expected devices, fixed IP intent, hostnames, and notes.
3. `services.yaml`: service names, ports, local URLs, remote URLs, and health
   checks.
4. `templates/compose/docker-compose.yml`: starter server runtime for Pi, mini
   PC, NAS, or another always-on Linux host.
5. `templates/compose/env.example`: public names for required local values,
   without secrets.
6. `homenet deploy --check-idempotent`: small deployment directory with README,
   commands, compose, env example, manifest, and repeat-generation proof.

## What It Does

- Describes a home network in a repeatable way.
- Shows which source tool owns each live setting.
- Gives a short deployment and adoption path.
- Keeps a low-dependency rescue path visible.
- Lets HomeNet and Kuma observe the same declared service inventory.

## What It Does Not Do

- It does not automatically rewrite a working router.
- It does not store Wi-Fi passwords, proxy subscriptions, tokens, keys, or
  runtime databases.
- It does not replace LuCI, Docker Compose, Cloudflare Dashboard, Mihomo
  Dashboard, AdGuard, WireGuard UI, Kuma, or Home Assistant.
- It does not require Pi for the model; Pi only makes service hosting easier.

## Existing Home Adoption

For a home that already works, the main path is:

```sh
./homenet deploy --instance instances/my-home --force --check-idempotent
./homenet check --instance instances/my-home
```

Then operate one source tool at a time:

1. OpenWrt: verify current WAN, LAN, DHCP, firewall, Wi-Fi, Maintenance Wi-Fi, modem
   route, and room AP intent. Apply only reviewed drift.
2. Server runtime: use the generated `runtime/` draft, copy `runtime/env.example`
   to `runtime/.env`, fill secret values there, and validate compose.
3. DNS/Proxy: configure AdGuard and Mihomo in their own files or dashboards.
4. Remote access: configure Cloudflare, Caddy/DDNS, and WireGuard in their own
   tools.
5. Observability: use HomeNet for explanation and Kuma for notifications.

The result should feel like deploying a normal home network from a small set of
configuration files, with HomeNet providing a map and checks instead of becoming
another heavy control system.
