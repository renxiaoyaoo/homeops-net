# HomeNet Operator Path

This page is the short path for people or AI assistants operating a HomeNet
home. It is intentionally smaller than the full command catalog.

HomeNet should be useful before it is impressive. The first job is to make
the current network understandable and recoverable when something breaks. The
open source model comes from that operating path, not from adding every possible
automation surface.

HomeNet has one model:

- **Instance**: one home, described by `site.yaml`, `devices.yaml`, and `services.yaml`.
- **Profile**: where capabilities run, such as `openwrt-only` or `openwrt-pi`.
- **Module**: one bounded capability, such as Gateway, DNS, Proxy, Remote Access, Observability, Maintenance Wi-Fi, Room AP, or Smart Home.
- **Evidence**: read-only proof from OpenWrt, Docker, systemd, Mihomo, AdGuard, WireGuard, Cloudflare, Kuma, or service probes.
- **Source tool**: the component that actually owns a setting. HomeNet explains and plans; it should not silently take ownership away from OpenWrt, Mihomo, AdGuard, Kuma, Cloudflare, or Home Assistant.

## Choose A Profile

Start with the profile, not with hardware shopping.

| Profile | Use When | What Changes |
| --- | --- | --- |
| `openwrt-only` | You want the cheapest and simplest deployment. | OpenWrt runs Gateway, DNS, Proxy, Remote Access, and lightweight status. Performance and history are limited. |
| `openwrt-pi` | You have a Pi, mini PC, NAS, or other always-on server runtime. | OpenWrt stays Gateway. The server runtime improves DNS UI/logs, Proxy capacity, monitoring, Ops, WireGuard, Cloudflare Tunnel, and service isolation. |
| `openwrt-mini-pc` | Same model as `openwrt-pi`, with more CPU/RAM/storage. | More capacity, not a different mental model. |

Pi is optional. It improves comfort, capacity, and history. It should not be a hard product boundary.

## First Deployment

Use this path for a new home:

```sh
./homenet profiles
./homenet init --name my-home --profile openwrt-pi
./homenet deploy --instance instances/my-home --force --check-idempotent
./homenet check --instance instances/my-home
```

Use source tools for live changes, one layer at a time. After each source-tool
change, verify before moving on:

```sh
./homenet check --instance instances/my-home --live
./homenet status --instance instances/my-home --live
./homenet doctor --instance instances/my-home --live
```

Use advanced review only after the main path is clear or when maintaining the
HomeNet core:

```sh
./homenet deploy --instance instances/my-home --dry-run
./homenet bundle --instance instances/my-home --output /tmp/homenet-review
./homenet modules --instance instances/my-home
```

Module internals, future apply, backup, executor, and release commands are
cataloged in `docs/function-boundary.md`; they are not part of daily operation.

For a server-runtime profile, `templates/compose/` provides a public Docker
Compose starting point. Copy it into a private deployment directory, fill a
local `.env`, and keep filled secrets, databases, certificates, WireGuard data,
Cloudflare credentials, and proxy subscriptions out of git.

Live writes are not a casual command. They require source-tool ownership, backups,
operator confirmation, live evidence, and post-change verification.

## Daily Use

Use HomeNet Ops as the daily entry when it exists. Its first screen should
answer the incident questions before it shows inventory. The same structure is
available from `homenet incident` as `decision_flow` and `recovery_matrix`:

- Is the Gateway/WAN reachable?
- Did the main 5G radio and backhaul SSID come up?
- Is the Room AP reachable?
- Are DNS and Proxy healthy?
- Are the Pi services healthy?
- Are remote access paths healthy?
- Are smart-home bridges and hubs healthy?
- Is the maintenance path available?

Use the CLI when you need structured text for humans or AI:

```sh
./homenet status --instance instances/my-home
./homenet incident --instance instances/my-home
./homenet topology --instance instances/my-home
./homenet doctor --instance instances/my-home
./homenet runbook --instance instances/my-home
```

These commands are read-only by default. They do not print Wi-Fi passwords,
tokens, proxy subscriptions, private keys, cookies, or session values.

## Troubleshooting

Use this order when the network is slow, unstable, or confusing:

1. HomeNet Ops: first-screen decision flow and recovery matrix.
2. `incident --live`: one-page decision flow, triage, maintenance path, safe entries, and next commands.
3. `status --live`: what should be up and what live evidence currently says.
4. `doctor --live`: likely issue category and first safe action.
5. `topology`: how Gateway, DNS, Proxy, Room AP, server runtime, and services are connected.
6. `runbook`: scenario-specific steps and source tools.
7. `check --live` or `verify --live`: only when deeper live evidence is needed.

Do not start by resetting routers or rewriting configs. First identify which
source tool owns the failing layer.

Typical recovery order after a power event:

1. Gateway/WAN.
2. Main 5G radio / backhaul SSID.
3. Room AP and wireless backhaul.
4. DNS and Proxy.
5. Pi runtime services.
6. Remote access and notifications.
7. Smart-home bridges and hubs.
8. Client-specific issues.

For Apple Home symptoms, keep the scope narrow. First prove Home Assistant is
reachable, the HomeKit Bridge port is listening, and the Apple TV/Home Hub is
reachable from Home Assistant. If those are healthy but Apple Home still fails,
run an explicit mDNS check for `_hap._tcp.local` before moving to iPhone/Home
app/iCloud state.

For devices that have both wired and Wi-Fi identities, model them as
`<device>` and `<device>-wifi`. Live status treats Wi-Fi as a fallback: if the
wired identity is absent while the Wi-Fi identity is present, check the cable,
switch port, DHCP binding, and the device's native network service state.

## Source Tool Ownership

HomeNet should reduce scattered knowledge, not duplicate every dashboard.

| Area | Source Tool |
| --- | --- |
| Gateway, DHCP, static leases, Firewall, VLAN, Wi-Fi | OpenWrt / LuCI / UCI |
| DNS policy and logs | AdGuard or OpenWrt dnsmasq/mosdns |
| Proxy rules, groups, controller | Mihomo |
| Remote LAN return path | WireGuard |
| HTTPS remote entries | Cloudflare Tunnel / Access / DNS |
| Notifications and uptime history | Uptime Kuma |
| Smart home devices and automations | Home Assistant / Zigbee2MQTT |
| Daily explanation, topology, links, review bundles | HomeNet |

## Public Core vs Private Instance

The open source project should contain reusable model, schemas, examples,
modules, checks, renderers, templates, and docs. A real home is an instance of
that model.

A real private home is one deployment instance. It proves the model can
describe a real home, but it is not the public template and must not leak
secrets or runtime data into the public core.

If the real-home instance needs to move out of a mixed private workspace, use
`homenet workspace --instance <path>` first. The Private Instance Boundary section
is the source of truth for that separation: copy only the instance YAML and
README files into the private instance directory or private repository, keep
runtime directories and source-tool state untracked, then validate the copied
instance with `check`, `status --live`, `workspace`, and `deploy --check-idempotent`. This separation is a
documentation and versioning move; it must not change OpenWrt, DNS, Proxy,
Cloudflare, Kuma, Docker, systemd, or any live network setting by itself.

Before publishing or handing work to another operator, run:

```sh
./homenet privacy --scope public
./homenet privacy --scope all --instance instances/my-home
./homenet package --instance instances/my-home --output-dir /tmp/homenet-public
./homenet package-check --dir /tmp/homenet-public
./homenet package-smoke --dir /tmp/homenet-public
./homenet workspace --instance instances/my-home
./homenet check --instance instances/my-home
./homenet deploy --instance instances/my-home --force --check-idempotent
```

Maintainers preparing an official public repo can additionally use
`release-candidate`, `publish-check`, `repo-init`, `publish-audit`,
`repo-publish`, and `repo-plan`. `release-candidate` creates the local public package and local public git repo
without adding a remote or pushing. `repo-init` defaults to a lightweight
review precheck so creating the local public repo is quick. `publish-check`,
`publish-audit --run-publish-check`, and confirmed
`repo-publish --confirm-push PUSH-HOMENET-PUBLIC` run the full package
smoke/onboarding gate before public release.

The exported public repo includes `.github/workflows/ci.yml`, so GitHub push
and pull request checks run the public privacy scan, example CI, package
manifest, package check, and package smoke without repository secrets.
