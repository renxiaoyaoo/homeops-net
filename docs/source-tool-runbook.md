# Source Tool Runbook

HomeNet describes intent and verifies evidence. Source tools still own live
configuration. Use this runbook when deploying a new home or adopting an
existing home into HomeNet.

Each source-tool change should follow the same loop:

1. Read intent: `homenet deploy --instance <instance> --force --check-idempotent`
   and `homenet check --instance <instance>`.
2. Back up the source tool or confirm the rollback path.
3. Change one source tool and one layer only.
4. Verify with `homenet verify --instance <instance> --live` or
   `homenet doctor --instance <instance> --live`.
5. Stop if the failure domain changes or the rescue path is not reachable.

## Gateway / OpenWrt

Owns: WAN, LAN, VLANs, DHCP, static leases, firewall, Wi-Fi, DNS handoff,
transparent proxy routing, management access, and the rescue/Maintenance network.

Before changing:

- Export or copy `/etc/config/network`, `/etc/config/dhcp`,
  `/etc/config/firewall`, and `/etc/config/wireless`.
- Confirm a low-dependency access path: wired LAN, Maintenance SSID, or local console.
- Confirm the router management IP and SSH/LuCI access.

Minimal setup:

1. Configure WAN and LAN first.
2. Configure DHCP ranges and static leases.
3. Configure SSIDs and network attachment.
4. Configure DNS forwarding to the chosen DNS layer.
5. Configure firewall zones and inter-zone access.
6. Add proxy/TProxy rules only after plain WAN, LAN, and DNS are proven.

Verify:

```sh
homenet status --instance <instance> --live
homenet doctor --instance <instance> --live
homenet check --instance <instance> --live
```

Rollback:

- Restore the saved OpenWrt config files.
- Restart only the affected service if possible: network, dnsmasq, firewall, or
  wireless.
- Use a physical or Maintenance access path if the main LAN path breaks.

## DNS Layer

Owns: local names, split DNS, upstream policy, domestic/direct DNS, foreign/proxy
DNS, and DNS listener placement.

Source tools: AdGuard Home, OpenWrt dnsmasq, mosdns, or an external resolver.

Before changing:

- Back up the DNS service config.
- Record the current router DHCP DNS advertisement and DNS forwarding target.
- Confirm direct WAN works before debugging DNS.

Minimal setup:

1. Start with one DNS listener and one router forwarding path.
2. Add local zones such as `.lan` or `.home.arpa`.
3. Add domestic/direct upstream policy.
4. Add foreign/proxy DNS policy only after basic resolution works.
5. Keep client DNS behavior consistent across LAN, IoT, Guest, and Maintenance networks.

Verify:

```sh
homenet status --instance <instance> --live
homenet doctor --instance <instance> --live
```

Rollback:

- Restore the DNS service config.
- Point OpenWrt DHCP/DNS back to a known-good resolver.
- Keep Maintenance/rescue DNS simple and independent of proxy policy.

## Proxy / Mihomo

Owns: explicit proxy endpoint, controller, proxy groups, rule providers,
fake-IP/TProxy policy, and route split.

Before changing:

- Back up the Mihomo config and provider files.
- Confirm the proxy subscription or provider secret exists outside git.
- Confirm normal direct browsing works before enabling transparent proxy.

Minimal setup:

1. Bring up Mihomo explicit proxy and controller.
2. Confirm proxy groups and providers load.
3. Verify domestic direct and foreign proxy behavior with explicit proxy.
4. Add OpenWrt TProxy/fake-IP routing after explicit proxy is healthy.
5. Keep LAN bypass rules for router, server runtime, and rescue paths.

Verify:

```sh
homenet status --instance <instance> --live
homenet doctor --instance <instance> --live
```

Rollback:

- Disable transparent proxy rules first.
- Restore the previous Mihomo config.
- Restart Mihomo only after config validation.

## Server Runtime

Owns: Docker Compose, systemd units, service volumes, service ports, and local
runtime placement on Pi, mini PC, NAS, or another always-on Linux host.

Before changing:

- Back up service volumes and databases for stateful services.
- Keep filled `.env` files outside git.
- Confirm SSH access to the server runtime.

Minimal setup:

1. Copy `templates/compose/docker-compose.yml` and
   `templates/compose/env.example` into a private deployment directory.
2. Fill `.env` locally.
3. Start infrastructure services before optional services.
4. Confirm expected ports are listening.
5. Add restart policies only after the services are healthy.

Verify:

```sh
homenet verify --instance <instance> --live
homenet status --instance <instance> --live
```

Rollback:

- Restore the previous compose file, env file, or systemd unit.
- Restore service volume backups for stateful services.
- Restart only the affected service group.

## Remote Access

Owns: WireGuard peers, Cloudflare Tunnel public hostnames, Cloudflare Access
apps, DNS records, DDNS entries, Caddy routes, and IPv6 direct entries.

Before changing:

- Back up WireGuard data and Caddy/cloudflared/DDNS configs.
- Confirm the local LAN target works before publishing it remotely.
- Use scoped Cloudflare tokens; do not store tokens in the instance directory.

Minimal setup:

1. Make the LAN service healthy first.
2. Add WireGuard or tunnel connectivity.
3. Add DNS/public hostname.
4. Add Access policy if the service is private.
5. Test from outside the LAN.

Verify:

```sh
homenet status --instance <instance> --live
homenet doctor --instance <instance> --live
```

Rollback:

- Disable the public hostname, tunnel route, or peer.
- Keep the local LAN service unchanged unless the LAN target itself is bad.

## Observability

Owns: HomeNet status surfaces, service directory, topology, runbooks, Kuma
monitor candidates, status pages, and alert review.

Before changing:

- Back up Kuma database before importing monitors.
- Decide which system owns notifications. Usually Kuma owns alerts; HomeNet
  owns explanation and triage.

Minimal setup:

1. Keep the service inventory accurate.
2. Generate or review Kuma candidates.
3. Import monitors only after backup.
4. Use HomeNet Ops/CLI for status, topology, and failure-domain diagnosis.

Verify:

```sh
homenet kuma --instance <instance>
homenet status --instance <instance>
homenet doctor --instance <instance> --live
```

Rollback:

- Restore Kuma database backup or remove the imported monitor set.
- Fix instance inventory before changing live monitor behavior again.

## Maintenance Wi-Fi / Rescue Path

Owns: low-dependency maintenance access for cases where DNS, proxy, or normal
client roaming is broken.

Before changing:

- Confirm at least one trusted maintenance device can join the rescue path.
- Keep the path simple: direct WAN, router access, server SSH, and no forced
  transparent proxy.

Minimal setup:

1. Put Maintenance Wi-Fi on a separate network or clearly bounded firewall zone.
2. Allow required maintenance targets only.
3. Avoid dependency on the normal DNS/proxy path.
4. Test from a phone or laptop before changing DNS or proxy globally.

Verify:

```sh
homenet rescue --instance <instance>
homenet status --instance <instance> --live
```

Rollback:

- Restore OpenWrt wireless/firewall config.
- Use wired or local console access if wireless maintenance access breaks.

## Room AP / Coverage

Owns: bedroom/room coverage, AP/relay settings, backhaul selection, and client
roaming behavior.

Before changing:

- Back up room AP config.
- Confirm how to reach the room AP if wireless backhaul fails.
- Keep DHCP authority on the main gateway unless the design explicitly says
  otherwise.

Minimal setup:

1. Configure LAN bridge or relay behavior.
2. Connect backhaul.
3. Broadcast room SSID or matching SSID according to the chosen roaming model.
4. Verify clients move to the stronger AP in the target room.

Current relayd note:

- From the main LAN, Pi, or the main OpenWrt gateway, manage the Room AP at
  `http://<room-ap-management-ip>/`.
- From a phone or laptop currently connected below the Room AP, manage the same
  device at `http://<room-ap-local-ip>/`.
- This split is expected for the current relayd deployment. A WDS/4addr or
  802.11s design can remove this split, but changing to it is a disruptive
  wireless-backhaul migration and must be planned as a dedicated change.
- 802.11r is optional. If hostapd repeatedly reports key-install failures or
  disconnects clients during transitions, disable FT consistently on all APs
  sharing the SSID. Keep 802.11k if useful; clients still perform ordinary
  roaming without FT.

Verify:

```sh
homenet status --instance <instance> --live
homenet doctor --instance <instance> --live
```

Rollback:

- Restore the room AP config.
- Disable the room AP SSID or relay if it causes duplicate DHCP, loops, or
  unstable roaming.

## Smart Home

Owns: Home Assistant, MQTT, Zigbee2MQTT, cameras, and optional smart-home
bridges.

Before changing:

- Back up Home Assistant and device bridge configs.
- Confirm network services are stable before debugging smart-home integrations.

Minimal setup:

1. Bring up MQTT or required bridges.
2. Bring up Home Assistant.
3. Add device integrations.
4. Add monitoring entries after services are stable.

Verify:

```sh
homenet status --instance <instance> --live
homenet doctor --instance <instance> --live
```

Rollback:

- Restore service config and database backups.
- Keep network-layer rollback separate from smart-home service rollback.
