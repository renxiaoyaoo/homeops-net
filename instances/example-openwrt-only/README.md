# Example Instance: OpenWrt Only

This is a public example for homes without Pi, mini PC, NAS, or another always-on server runtime.

- OpenWrt owns Gateway, DNS, Proxy, Remote Access, lightweight status, and maintenance Wi-Fi.
- The profile keeps the same HomeNet capability model, but some modules run in lightweight mode.
- Secrets are intentionally absent. Put Wi-Fi passwords, API tokens, proxy subscriptions, and private keys in local secret storage.

First pass:

```sh
./homenet deploy --instance instances/example-openwrt-only --force --check-idempotent
./homenet check --instance instances/example-openwrt-only
```

Review before live changes:

```sh
./homenet deploy --instance instances/example-openwrt-only --dry-run
./homenet rollback --instance instances/example-openwrt-only
./homenet apply --instance instances/example-openwrt-only --dry-run
./homenet bundle --instance instances/example-openwrt-only --output /tmp/homenet-example-review
./homenet check --instance instances/example-openwrt-only
```
