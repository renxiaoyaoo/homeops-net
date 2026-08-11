# Example Instance: OpenWrt + Server

This is a public example for the standard HomeNet profile.

- OpenWrt owns Gateway, DHCP, Firewall, Wi-Fi, VLAN/network boundaries, and TProxy handoff.
- A server runtime such as Pi, mini PC, or NAS owns AdGuard, Mihomo, HomeNet Ops, Uptime Kuma, WireGuard, and Cloudflare Tunnel.
- Secrets are intentionally absent. Put Wi-Fi passwords, API tokens, proxy subscriptions, and private keys in local secret storage.

First pass:

```sh
./homenet deploy --instance instances/example-openwrt-pi --force --check-idempotent
./homenet check --instance instances/example-openwrt-pi
```

Review before live changes:

```sh
./homenet status --instance instances/example-openwrt-pi
./homenet runbook --instance instances/example-openwrt-pi
./homenet deploy --instance instances/example-openwrt-pi --dry-run
./homenet rollback --instance instances/example-openwrt-pi
./homenet apply --instance instances/example-openwrt-pi --dry-run
```
