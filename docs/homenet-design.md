# HomeNet Design

HomeNet is an open source home network blueprint for people who want a reliable, maintainable home network with transparent proxying, DNS split, remote access, monitoring, and a clear operations console.

The project should not be a copy of one home network. It should provide a reusable system model, deployment tooling, defaults, and documentation. A real home is one deployment instance of that model.

## 1. Problem

Home networks become hard to maintain when several needs are solved independently:

- Domestic apps should stay direct and fast.
- Foreign apps and AI services should work without manual proxy toggling.
- Devices should work the same at home and, where possible, outside home.
- Home services should have clear local and remote entry points.
- DNS, proxy, DHCP, Wi-Fi, tunnels, monitoring, and smart home services should not be scattered across unrelated dashboards.
- When the network breaks, there should still be a predictable maintenance path.
- The owner should be able to understand what exists, what is healthy, and what changed.

Most existing solutions are either too raw, such as only OpenWrt/Mihomo snippets, or too opaque, such as consumer mesh routers and cloud apps. HomeNet sits in the middle: professional terms and real control, but low operational confusion.

## 2. Product Position

HomeNet is a home network operations system, not only a proxy setup.

It provides:

- **Instance Model**: a structured description of one home, including networks, SSIDs, devices, services, ports, domains, runtime targets, and pluggable modules.
- **Blueprint**: a product/instance contract that summarizes problems, provided capabilities, non-goals, operational questions, source-of-truth ownership, and active/fallback capabilities.
- **Planner**: reads the instance and decides where modules should run: OpenWrt, Pi, mini PC, or external/cloud services.
- **Modules**: reusable implementations for Gateway, DNS, Proxy, Remote Access, Observability, Ops integration, and optional Smart Home services.
- **Checker**: read-only validation that compares the declared instance with live evidence from OpenWrt, Docker, systemd, Mihomo, AdGuard, WireGuard, and Cloudflare.
- **Ops**: the daily home operations surface for status, service entries, topology, access paths, and troubleshooting. The HomeNet root owns the metadata contracts and integration surfaces it consumes.
- **Apply/Rollback workflow**: generated changes, backups, cautious apply order, and recovery instructions.
- **Private Instance Layer**: per-home files and secrets outside the open source core, so a real home can use the common system without publishing private values.

It should feel like a serious home infrastructure product: clear enough for a technical home user, not reduced to a beginner toy.

Technical vocabulary should stay recognizable. Terms such as Gateway, DNS, Proxy, Tunnel, SSID, DHCP, VLAN, TProxy, WireGuard, metadata, artifacts, and Cloudflare Access are part of the product language. HomeNet explains what each term does in this home instead of replacing every term with oversimplified wording.

## 3. Users

### 3.1 Primary User

A technical home user who can flash OpenWrt, SSH into a device, and understand terms like DNS, proxy, LAN, and WireGuard, but does not want to manually maintain dozens of ad hoc scripts.

### 3.2 Maintainer

The person who debugs the network after months. This may be the original owner, another family member, or an AI assistant with SSH access. The maintainer needs accurate state, known entry points, and a document that maps names to actual services.

### 3.3 Instance Owner

The person operating a specific home. They should be able to keep private values out of git while still using the open source core.

## 4. Product Contract

HomeNet should answer five practical questions for any supported home:

1. What is this network supposed to look like?
   The answer comes from the instance files: `site.yaml`, `devices.yaml`, `services.yaml`, and private secret files.

2. What is actually running now?
   The answer comes from read-only evidence: OpenWrt UCI/runtime state, DHCP leases, Docker, systemd, Mihomo API, AdGuard config/API, WireGuard state, Cloudflare Tunnel, and service probes.

3. How does traffic move?
   The answer should show Gateway, DNS, Proxy, TProxy, DIRECT, WireGuard, Cloudflare Tunnel, and local service paths without hiding those terms.

4. Where should a person go for each task?
   HomeNet Ops is the daily entry. Source tools remain available for deep work: LuCI, Mihomo Dashboard, AdGuard, Uptime Kuma, Home Assistant, Cloudflare Dashboard, and WireGuard UI.

5. If something breaks, what is the safe maintenance path?
   The design must keep local IP entries, Maintenance Wi-Fi, SSH paths, backups, and rollback steps visible. Recovery must not require guessing which script or dashboard owns a setting.

The project succeeds when a maintainer can read the instance, run `homenet check`, open HomeNet Ops, and understand both the intended architecture and the current deviation from it.

`homenet blueprint` is the first context-building command. It should answer what the project is for and what the current instance enables before the operator reads module-level `plan`, generated `metadata`, or apply-before `artifacts`.

## 5. Non-Goals

- It is not a consumer mesh replacement.
- It is not a turnkey black-box VPN product.
- It does not promise to hide VPN/proxy usage from hostile apps or platforms.
- It does not require Pi. Pi is a runtime target, not a product tier.
- It does not require Cloudflare. Cloudflare is one remote entry module.
- It should not auto-reset routers, auto-redial WAN repeatedly, or perform risky recovery loops without explicit operator action.
- It should not expose real secrets, subscriptions, private keys, passwords, tokens, account IDs, or private runtime databases.
- It should not duplicate every feature of source tools. HomeNet explains and links; it only controls when that control is safer and clearer than using the source tool directly.
- It should not require every home to run Home Assistant, Cloudflare, Uptime Kuma, or a Pi.

## 6. Design Principles

1. Keep concepts honest.
   Use names like OpenWrt Gateway, Mihomo Proxy, AdGuard DNS, WireGuard, Cloudflare Tunnel, and Maintenance Wi-Fi. Add short role descriptions instead of hiding the terms.

2. Keep English technical terms where they carry real meaning.
   Use mixed technical language deliberately: Gateway / 网关, DNS / 解析, Proxy / 代理, Tunnel / 隧道, SSID / Wi-Fi 名称, DHCP / 自动分配地址, VLAN / 网络隔离, TProxy / 透明代理接管, WireGuard / 回家隧道, artifacts / 生成产物清单. The Chinese explanation should clarify the role, not erase the operational term.

3. Do not over-simplify the operator surface.
   The UI and docs should reduce confusion, not remove precise terms. Prefer "Mihomo Proxy 负责规则分流和节点选择" over "帮你上国外网站"; prefer "OpenWrt Gateway owns DHCP/static leases" over "路由器分配地址". The reader should learn the actual architecture while operating it.

4. Same capability model, different runtime targets.
   Pi, mini PC, and OpenWrt-only deployments should share the same feature model. Hardware decides placement and performance, not the conceptual product.

5. Every advanced module needs a fallback.
   For example, AdGuard DNS can fall back to dnsmasq/mosdns; Uptime Kuma can fall back to basic probes; HomeNet full console can fall back to a lightweight status page.

6. Deploy from declared intent.
   The instance says what it wants. The planner decides where each module runs and what configs must be produced.

7. Always leave a maintenance path.
   Maintenance Wi-Fi, local IP entry points, backup configs, and rollback plans are first-class.

8. Separate evidence from interpretation.
   OpenWrt, Mihomo, AdGuard, Docker, systemd, WireGuard, and Cloudflare remain sources of truth. HomeNet explains their evidence; it should not silently invent state.

9. Minimize required choices.
   Advanced options exist, but default profiles should work with only a few required inputs.

10. Avoid script sprawl.
   A script is acceptable when it wraps one clear module operation. Long-term behavior should become a declared module, generated config, systemd unit, container, or HomeNet check instead of scattered one-off shell.

11. Use source-of-truth ownership.
    DHCP/static leases belong to OpenWrt. DNS behavior belongs to AdGuard/dnsmasq/mosdns. Proxy behavior belongs to Mihomo. Notifications belong to Kuma. HomeNet may summarize them, but the instance must record which component owns each fact.

## 7. What The Open Source Project Ships

The public project should ship these layers:

```text
homenet/
  core/
    planner/
    checker/
    renderer/
    secrets/
  modules/
    catalog.yaml
    artifacts.yaml
    renderers.yaml
    README.md
  profiles/
    openwrt-only.yaml
    openwrt-pi.yaml
    openwrt-mini-pc.yaml
  schemas/
  templates/
  docs/
  examples/
```

### 7.1 Core

Core owns the stable product logic:

- Parse and validate instance files.
- Resolve defaults and profile choices.
- Build a plan from desired state to generated artifacts.
- Run read-only checks.
- Render HomeNet metadata.
- Enforce privacy rules.

Core should not contain real-home domains, devices, passwords, proxy subscriptions, or Cloudflare account values.
The module catalog, artifact catalog, renderer catalog, and implementation index are the normal source for module metadata. Module definitions, source-tool boundaries, artifact ownership, renderer ownership, and implementation ownership belong under `modules/`.

### 7.2 Modules

A module is a bounded unit with four surfaces:

- `inputs`: the fields it reads from the instance.
- `outputs`: configs, commands, service definitions, dashboards, or checks it produces.
- `evidence`: live sources used to verify it.
- `rollback`: what must be backed up and how to restore it.

Example:

```text
proxy-mihomo
inputs: proxy providers, rule groups, DNS fake-ip ranges, runtime target
outputs: mihomo config, systemd/container service, OpenWrt TProxy handoff if off-router
evidence: Mihomo controller API, generated config hash, route behavior checks
rollback: previous config, previous service state, previous OpenWrt policy rules
```

### 7.3 Profiles

Profiles are placement defaults, not separate products:

- `openwrt-only`: maximum simplicity, lower performance, fewer long-running services.
- `openwrt-pi`: standard home deployment with good stability and observability.
- `openwrt-mini-pc`: same model with more capacity.

The same instance should be able to say `runtime: auto` and let the planner choose a profile based on available hardware.

Planner output must include a capability matrix, not only a placement list. For each module, the matrix should state:

- Whether the capability is required or optional.
- Which runtime options are supported.
- What the current instance selected.
- What the OpenWrt-only fallback is.
- What improves when a Pi, mini PC, NAS, or other server runtime exists.

This keeps Pi optional without hiding tradeoffs. A Pi should improve performance, history, Docker services, and operational comfort; it should not be a hard product boundary.

Deployment promise:

- OpenWrt-only must remain a valid deployment shape, not a demo-only fallback.
- Adding a Pi, mini PC, NAS, or other server runtime should mostly improve capacity, history retention, UI comfort, and service isolation.
- Features that are too heavy for OpenWrt should have a lower-cost substitute, such as lightweight probes instead of full observability, dnsmasq/mosdns instead of AdGuard, or router-local status instead of full Ops.
- The operator should learn one model: instance, profile, module, artifact, evidence, rollback. Hardware changes placement; it should not force a different mental model.
- Autodeploy should be possible from declared intent, but write-side apply must stay gated by privacy checks, backup contracts, generated artifact review, and live verification.

### 7.4 Instance

An instance is one real deployment:

```text
instances/my-home/
  site.yaml
  devices.yaml
  services.yaml
  secrets.env        # local only, ignored by git
  overrides/
```

The instance records intent and inventory. It should be readable by people and machines. It should avoid private secrets and runtime databases.

Public examples should live beside private deployment instances, but must not include real private values:

```text
instances/example-openwrt-pi/
instances/example-openwrt-only/
instances/<private-home>/    # private deployment instance, not part of public package
```

Examples are part of the product contract. They lower understanding cost, prove schemas are not tied to one home, and give future automation stable fixtures.

The CLI should provide a first-run smoke test and scaffold path:

```text
homenet profiles
homenet quickstart --profile openwrt-pi
homenet module-definitions
homenet module-artifacts
homenet module-renderers
homenet module-implementations
homenet modules --generic
homenet modules --instance instances/example-openwrt-pi
homenet ownership --instance instances/example-openwrt-pi
homenet inputs --instance instances/example-openwrt-pi
homenet worksheet --instance instances/example-openwrt-pi
homenet adopt --instance instances/example-openwrt-pi
homenet deploy --instance instances/example-openwrt-pi --force --check-idempotent
homenet privacy --scope public
homenet release --instance instances/example-openwrt-pi
homenet version --instance instances/example-openwrt-pi
homenet status --instance instances/example-openwrt-pi
homenet examples
homenet examples --json
homenet bundle --instance instances/example-openwrt-pi --output /tmp/homenet-review
homenet ci --instance instances/example-openwrt-pi
homenet init --name my-home --profile openwrt-pi
homenet init --name my-mini-home --profile openwrt-mini-pc
homenet init --name my-router-only --profile openwrt-only
```

`homenet profiles` lists reusable deployment shapes before a real instance exists. It should show hardware assumptions, required inputs, tradeoffs, example instances, scaffold commands, and the capability matrix for each profile.

`homenet quickstart` is the low-understanding-cost first deployment guide. It first emits an operator summary for first deployment, daily use, incident response, and public/private boundaries, then shows the detailed staged workflow. Advanced review surfaces such as deploy dry-run, rollback, apply dry-run, gates, evidence, render, and generate remain discoverable, but they are not part of the first public deployment path. It must not read secret values or write live state.

`homenet adopt` and `homenet deploy --check-idempotent` are the practical
deployment checkpoints. They keep the path shorter than the full review/apply
contract, produce a minimal deployment package, and prove repeat generation is stable.

`homenet module-definitions` reads `modules/catalog.yaml` and emits the public, versioned module definition layer. It is generic product metadata and contains no private deployment values.

`homenet module-artifacts` reads `modules/artifacts.yaml` and emits the public, versioned artifact contract layer. It is generic product metadata for review/future apply surfaces and contains no rendered config values or private deployment values.

`homenet module-renderers` reads `modules/renderers.yaml` and emits the public, versioned renderer contract layer. It maps review renderers to module artifacts and records review/deployable status plus privacy class without rendered config values.

`homenet module-implementations` reads `modules/implementations.yaml` and emits the public, versioned implementation index. It maps renderer contracts to their current source surface and records whether they are still centralized, review-only, and write-disabled.

`homenet modules` lists the reusable capability catalog before apply or deployment work. `--generic` shows the open source module model with generic inputs, outputs, checks, rollback, source-tool boundaries, and apply policy for every module; with `--instance`, it overlays current status, placement, intent, instance-specific surfaces, and Module Decisions. Module Decisions explain whether a module is required or optional, when to enable or disable it, what disabling changes, the fallback, and which `site.yaml modules.<id>` fields to edit.

`homenet ownership` lists source-of-truth ownership and write boundaries. It clarifies what is owned by instance files, OpenWrt, DNS, Proxy, Tunnel, WireGuard, Kuma, Ops, and service runtimes, so the operator knows where to inspect or modify state without duplicating responsibilities. It must also expose future writer ownership for guarded apply, mapping each writer to its source tool, write surface, artifact count, backup count, and `source_tools.reviewed` evidence key.

`homenet inputs` lists the deployment input checklist for one instance. It bridges `secrets` and `preflight`: it explains what the operator must provide, what the instance already declares, and what HomeNet derives automatically, without reading secret values or live state.

`homenet worksheet` turns inputs, secrets, preflight, readiness, and deploy dry-run into a human operator worklist. It groups work by instance files, runtime targets, networks/Wi-Fi, secrets, operator preflight, and review gates, while still showing only secret names and storage hints.

`homenet deploy --dry-run` lists the end-to-end deployment workflow for one instance. It coordinates inputs, secrets, preflight, bundle review, rollback, generated config review, future apply contract, and live verify without writing files or live configuration.

It also exposes the current config review summary and backup contract summary so the deployment overview shows whether review artifacts and backup capture/restore/verify plans are complete before the operator opens the lower-level apply plan.

`homenet bootstrap` lists the first-install or adoption bootstrap plan for one instance. It coordinates safe read-only commands, source-tool actions, source-tool setup sequence, secret prerequisites, rollback/apply contracts, and live verification order without writing files or live configuration.

`homenet privacy` scans public source files and/or instance files for private values without printing matched content. It reports only path, line, severity, and risk type.

`homenet release` reports the public release boundary. It marks public core roots, excluded private/runtime roots, review-required directories, and the rule that the whole live worktree is not publishable.

`homenet version` reports the current core version, git state, workspace project ownership, instance profile, and release-boundary summary. It answers where the work is being versioned without reading secrets or live network state, and makes clear that the Ops app source is a sibling project while the root owns its metadata/integration contracts.

`homenet status` is the daily operator summary and diagnostic-first Ops contract. It emits `homenet.status.v1`, combining a `diagnostic_surface`, daily entries, runtime targets, networks, SSIDs, module state, remote ingress, maintenance paths, and optional read-only live findings. The diagnostic surface is the first-screen model: Gateway/WAN, Wi-Fi radios, Room AP, DNS/Proxy, Server Runtime, Remote Access, Rescue Path, and Client/Device Identity. Each domain names the first probe, follow-up proof, owning source tool, linked services, paired remote entries where relevant, and the action to take if the domain is bad. With `--live`, warning/failure findings are classified into those domains so Ops can mark the affected layer instead of showing raw probe text only.

`homenet examples` must stay read-only and offline with respect to live home infrastructure. It validates public examples, builds plans, exports metadata, renders generated docs, and summarizes Kuma candidates. Private deployment instances are included only when explicitly requested with `--all`.

`homenet bundle` creates a complete read-only review package for one instance. It is useful for humans, AI assistants, CI, and future apply review because every generated surface is captured together with a manifest.

`homenet ci` aggregates the public privacy audit, instance privacy audit, public examples, selected instance verify, incident/quickstart/workspace surface checks, render preview, and bundle smoke into one read-only gate. It is the command to run before publishing, handing an instance to an AI maintainer, or wiring future automation.

`homenet workspace` is the mixed-directory boundary report. It lists the HomeNet root including `apps/ops/`, private Worker projects such as `sub/`, public examples, private deployment instances, and ignored runtime state as separate ownership boundaries with commit-from and publish-scope rules. It also exposes Private Instance Boundary: the target shape for keeping a real-home instance inside the network workspace while excluding it from public git, the files to copy, the runtime paths to leave untracked, validation commands, and no-live-change rules. It exists so a human or AI maintainer does not treat the whole live workspace as one publishable repository or one live adoption batch.

`homenet progress` is the implementation progress report for the reusable core plus one selected instance. It must be explicit about what the percentage means: public model, examples, instance validity, operator surfaces, config review renderers, safety boundaries, deployment automation contracts, and live/apply maturity. It should show evidence and remaining work, and it must not imply that live write-side apply is complete while apply remains intentionally disabled. Public release evidence has two layers: `docs/public-release.json` is the stable published-release anchor, while an available local public repo checkout can add the current HEAD, dirty state, and redacted remote so the operator can see the latest synced public state without trying to store a self-referential commit hash in the same commit.

`homenet init` creates an editable instance draft from a public example template. It must not write secrets, must refuse to overwrite existing directories by default, and must produce an instance that passes `homenet verify --instance <path> --skip-examples`. The generated instance README must include first-pass commands plus deploy dry-run, rollback, apply dry-run, render, bundle, and CI review commands.

## 8. Core Capabilities

### 8.1 OpenWrt Gateway

Responsibilities:

- WAN, PPPoE or DHCP uplink.
- LAN, DHCP, DNS forwarding.
- Wi-Fi SSIDs and optional network isolation.
- Policy routing and firewall boundaries.
- TProxy handoff when proxy runs off-router.
- Static DHCP leases.
- Maintenance network, if enabled.

Default networks:

- Main LAN: daily devices.
- IoT Network: smart home and cameras.
- Guest Network: isolated guest access.
- Maintenance Wi-Fi: maintenance access with minimal LAN reachability.

### 8.2 DNS Layer

Responsibilities:

- Domestic domain real DNS resolution.
- Foreign or non-domestic domain handoff to proxy DNS or fake-ip.
- Optional blocking and query visibility.

Implementations:

- Full: AdGuard DNS on Pi or mini PC.
- Lightweight: dnsmasq/mosdns on OpenWrt.
- External: user-supplied DNS server.

### 8.3 Mihomo Proxy

Responsibilities:

- Rule-based transparent proxying.
- Explicit proxy entry for clients that need it.
- AI/foreign software route groups.
- Domestic direct bypass.
- Optional shared or user-owned proxy providers.

Runtime placement:

- OpenWrt if hardware can handle it.
- Pi or mini PC for standard deployments.
- External host for advanced or remote sites.

Provider modes:

- User subscription only.
- Shared subscription only.
- Mixed: user subscription as primary, shared subscription as fallback or special groups.

### 8.4 Remote Access

Responsibilities:

- Access LAN services from outside.
- Provide remote maintenance routes.
- Avoid exposing unnecessary ports.

Implementations:

- WireGuard for LAN-level return path.
- Cloudflare Tunnel / Access for selected HTTPS services.
- DDNS + IPv6 direct entry where appropriate.

### 8.5 Observability

Responsibilities:

- Show whether the network is healthy.
- Explain which path traffic is taking.
- Alert on service downtime.
- Keep enough history to debug intermittent issues.

Implementations:

- Full: Uptime Kuma + HomeNet Ops + logs.
- Lightweight: periodic probes and last-known status.

### 8.6 HomeNet Ops

Responsibilities:

- Daily home entry point.
- Current status across network, services, remote access, and maintenance paths.
- Service directory with local and remote links.
- Topology that reflects the actual deployment instance.
- Fix paths based on symptoms.
- Read-only health checks by default.

HomeNet should not replace source tools:

- OpenWrt remains gateway source of truth.
- Mihomo Dashboard remains proxy source of truth.
- AdGuard remains DNS/query source of truth.
- Uptime Kuma remains alerting source of truth.
- Home Assistant remains smart home source of truth.

### 8.7 Instance Inventory

Responsibilities:

- Device names, fixed IPs, owners, roles, and expected network.
- Services and ports by host.
- External domains and their upstreams.
- Wi-Fi and network purposes.
- Maintenance commands and recovery paths.

## 9. Runtime Profiles

Profiles should be output of planning, not separate products.

### 9.1 OpenWrt Only

Use when no Pi or mini PC exists.

Expected placement:

- OpenWrt Gateway on router.
- DNS on router.
- Mihomo on router if resources allow.
- Lightweight HomeNet/status only.
- WireGuard on router if enabled.

Tradeoffs:

- Lower performance.
- Less history.
- Fewer Docker-based services.
- Simpler hardware.

### 9.2 OpenWrt + Pi

Standard target.

Expected placement:

- OpenWrt handles gateway, Wi-Fi, DHCP, firewall, and policy routing.
- Pi handles AdGuard, Mihomo, HomeNet, Kuma, WireGuard, Cloudflare Tunnel, Caddy, and optional smart home services.

Tradeoffs:

- Better stability and observability.
- OpenWrt stays focused.
- More moving parts than OpenWrt-only.

### 9.3 OpenWrt + Mini PC

Enhanced target.

Expected placement:

- Same as Pi profile, but with more services, longer history, and heavier workloads.

Tradeoffs:

- More capacity.
- Higher cost and power usage.

## 10. Configuration Model

The open source core should not contain private home data. A deployment is described by an instance directory.

Example structure:

```text
homenet/
  core/
  modules/
  profiles/
  templates/
  docs/
  tools/
  instances/
    example/

my-home-private/
  site.yaml
  devices.yaml
  services.yaml
  secrets.env
  overrides/
```

The current `/home/pi/network` is closer to an instance plus prototype core. The implementation work should extract reusable parts into core/modules and leave private values in instance files.

### 10.1 Site Config

Example:

```yaml
site:
  name: my-home
  domain: example.com

runtime:
  router:
    type: openwrt
    host: 192.168.90.1
  server:
    enabled: auto
    preferred: pi
    host: 192.168.90.5

networks:
  lan:
    cidr: 192.168.90.0/24
  iot:
    enabled: true
    cidr: 192.168.91.0/24
  guest:
    enabled: true
    cidr: 192.168.92.0/24
  ops:
    enabled: true
    cidr: 192.168.93.0/24

modules:
  dns-layer:
    enabled: true
    runtime: auto
    implementation: auto
    fallback: openwrt:dnsmasq
  proxy-mihomo:
    enabled: true
    runtime: auto
    implementation: mihomo
    fallback: explicit proxy
  remote-access:
    enabled: true
    runtime: auto
    methods:
      - wireguard
      - cloudflare_tunnel
  observability-homenet:
    enabled: true
    runtime: auto
    implementation: auto
    level: auto
```

### 10.2 Secrets

Secrets stay outside git:

```text
MIHOMO_SUB_URL=
CLOUDFLARE_ACCOUNT_ID=
CLOUDFLARE_API_TOKEN=
WIREGUARD_ADMIN_PASSWORD=
WIFI_MAIN_PASSWORD=
WIFI_IOT_PASSWORD=
```

Tools must never print secret values. They may print whether a required secret is present.

## 11. Deployment Workflow

The deployment tool should expose these read-only surfaces before any write-capable apply workflow exists:

```text
homenet blueprint
homenet profiles
homenet plan
homenet metadata
homenet secrets
homenet preflight
homenet readiness
homenet rollback
homenet evidence
homenet artifacts
homenet apply --dry-run
homenet render --dry-run
homenet generate --dry-run
homenet rescue
homenet runbook
homenet topology
homenet incident
homenet doctor
homenet scripts
homenet status
homenet ownership
homenet bundle
homenet docs
homenet kuma
homenet check
homenet verify
homenet examples
homenet init
```

Write-capable commands are future work and must be built on top of those read-only contracts:

```text
homenet apply
homenet rollback
```

### 11.1 Blueprint

`homenet blueprint` is the top-level product/instance contract. It consumes the same instance state as `homenet plan`, `homenet metadata`, and `homenet artifacts`, then emits `homenet.blueprint.v1`.

It provides:

- Problem statements: why this system exists.
- Provides: the concrete product surfaces such as Instance Model, Planner, Checker, Ops, generated docs, Kuma inventory, and Artifacts manifest.
- Non-goals: what HomeNet intentionally does not promise.
- Operational Questions: where to look for intended state, live evidence, traffic path, source-tool entry, and future apply changes.
- Active / fallback capabilities from the runtime capability matrix.
- Source-of-truth ownership for OpenWrt, DNS, Proxy, WireGuard, Cloudflare Tunnel, Kuma, Ops, and instance files.

Blueprint should keep professional terms such as Gateway, DNS, Proxy, TProxy, WireGuard, Cloudflare Tunnel, metadata, and artifacts. It is a context surface, not a beginner rewrite and not a replacement for detailed module outputs.

### 11.2 Profiles

`homenet profiles` is the deployment-shape catalog. It emits `homenet.profiles.v1`.

It provides:

- Supported profile IDs such as `openwrt-pi`, `openwrt-mini-pc`, and `openwrt-only`.
- Hardware assumptions and default server runtime.
- Required inputs before scaffold or apply.
- Tradeoffs for performance, observability, maintenance cost, and fallback.
- Example instance path and scaffold command.
- Capability matrix derived from the shared module capability model.

Profiles are not deployment instances. They contain no private domain, devices, passwords, proxy subscriptions, tokens, or runtime data.

### 11.2.1 Modules

`homenet module-definitions` is the public module source. It reads `modules/catalog.yaml` and emits `homenet.module_definitions.v1`.

`homenet module-artifacts` is the public artifact contract source. It reads `modules/artifacts.yaml` and emits `homenet.module_artifacts.v1`.

`homenet module-renderers` is the public renderer contract source. It reads `modules/renderers.yaml` and emits `homenet.module_renderers.v1`.

`homenet module-implementations` is the public implementation index source. It reads `modules/implementations.yaml` and emits `homenet.module_implementations.v1`.

`homenet modules` is the capability catalog derived from the public module definitions, with optional instance placement overlaid. It emits `homenet.modules.v1`.

It provides:

- Reusable module IDs, titles, required/optional status, runtime options, and fallback.
- Profile support for OpenWrt-only, OpenWrt + Pi, and OpenWrt + mini PC style deployments.
- Source-tool ownership, module boundaries, and apply policy.
- Current instance status and placement when an instance is provided.
- Module surfaces: inputs, generated outputs, checks, and rollback.

The modules catalog is intentionally between `profiles` and `plan`: profiles answer which deployment shape fits, modules answer what capabilities exist, and plan answers how a specific home maps those capabilities onto real devices.

### 11.3 Plan

Reads instance config, then shows:

- Detected OpenWrt target.
- Detected server target, if any.
- Module placement decisions.
- Module-level Inputs, Outputs, Checks, and Rollback points.
- Config files to generate.
- Router changes to apply.
- Services to start or update.
- Rollback points that will be created.

### 11.4 Metadata

`homenet metadata` is a read-only export surface. It renders `homenet.metadata.v1` from the same instance and planner state used by `homenet check` and `homenet plan`.

It provides normalized machine-readable data for:

- HomeNet Ops service directory and port inventory.
- Documentation generation.
- Uptime Kuma monitor candidates.
- Future config generators and apply previews.

The metadata export must not include passwords, tokens, private keys, cookies, sessions, or proxy subscription URLs. It may include whether a service has a local URL, remote URL, port, owner, runtime, module placement, Checks, and Rollback.

### 11.5 Secrets

`homenet secrets` is the secret prerequisite contract. It consumes the instance and emits `homenet.secrets.v1`.

It provides:

- Expected secret names.
- Scope, such as Wi-Fi, Proxy, Remote Access, Cloudflare, DNS, Smart Home, or operator SSH.
- Whether the secret is required or optional for the declared instance.
- Which modules use it.
- Purpose and storage hint.
- Placeholder env template output for local secret stores when `--template` is explicit.

The command must not read local secret stores, validate secret values, print real values, or write any files. `--template` may print shell/env-style placeholders so an operator can fill a local secret store, but those placeholders must remain fake public values. It exists so a future deploy/apply workflow can fail early with a clear missing-prerequisite list instead of discovering secret gaps halfway through a network change.

### 11.6 Inputs

`homenet inputs` is the deployment input checklist. It emits `homenet.inputs.v1`.

It provides:

- Profile required inputs from the selected deployment shape.
- Required instance files and their purpose.
- Runtime targets such as OpenWrt Gateway, server runtime, and optional Room AP.
- Declared networks, Wi-Fi, module placement, and required secret names.
- Auto defaults that HomeNet derives from the instance, such as profile, module placement, service directory, and Kuma candidates.

The command must not read secret stores, validate secret values, query live infrastructure, mutate files, or write devices. It is for first deployment and review: it answers what still needs to be provided before preflight and apply review.

### 11.7 Preflight

`homenet preflight` is the local operator prerequisite report. It consumes the instance, secret contract, evidence plan, and local command availability, then emits `homenet.preflight.v1`.

It provides:

- Required and optional command presence, such as `python3`, `ssh`, `curl`, `docker`, and `systemctl`.
- Python runtime dependency presence.
- Required secret name presence in approved local env sources.
- Compatible secret aliases used by existing deployments, without printing values.
- Which required secrets must be confirmed in device/service-native storage, such as Wi-Fi, SSH, or WireGuard state.
- Concrete next actions before live verification or future apply work.

The command must not print secret values, query live OpenWrt, call Cloudflare, inspect Docker, mutate files, or write devices. It is different from `readiness`: preflight checks the operator machine's local prerequisites, while readiness checks whether generated review/apply contracts are coherent.

### 11.8 Readiness

`homenet readiness` is the offline maintenance gate. It consumes the same instance state and generated contracts as `homenet plan`, `homenet metadata`, `homenet secrets`, `homenet artifacts`, and `homenet kuma`, then emits `homenet.readiness.v1`.

It provides:

- `ready_for_review`, for deciding whether the instance is coherent enough for human or AI review.
- `ready_for_apply`, for deciding whether a future write path may safely proceed.
- Review blockers from instance validation failures.
- Apply blockers such as unimplemented apply, unverified secret values, and missing live evidence.
- Warnings for network-disruptive artifacts, service restarts, remote entry changes, database writes, manual Kuma candidates, and offline-only evidence.
- Concrete next actions.

The command is intentionally offline. It must not read secret values, query live OpenWrt, call Cloudflare, inspect Docker, mutate Kuma, render configs, or write devices. It can say that an instance is ready for review while still refusing to claim it is ready for apply.

### 11.9 Rollback

`homenet rollback` is the read-only backup and rollback contract. It consumes `homenet.plan.v1` and `homenet.artifacts.v1`, then emits `homenet.rollback.v1`.

It provides:

- Module rollback sources declared by the plan.
- Backup sources inferred from planned artifacts that require backup.
- Backup plan entries with capture, restore, and verify plans for each backup-required artifact.
- Per-module artifact count and risk summary.
- Preflight instructions for future apply.
- Recovery order that keeps the maintenance path, gateway, DNS, proxy, remote access, AP coverage, server runtime, observability, and smart-home services understandable during recovery.

The command must not execute backups, restore files, write devices, restart services, read secret values, or inspect live infrastructure. Capture, restore, and verify entries are plans for source tools, not commands HomeNet runs in the current build. It exists so future apply work has a mandatory safety contract before any write path is implemented.

### 11.10 Evidence

`homenet evidence` is the read-only live evidence plan. It consumes the instance, maps module-owned live checks to HomeNet modules, and emits `homenet.evidence.v1`.

It provides:

- Evidence groups such as HomeNet API, systemd, Docker, Pi TProxy, OpenWrt policy, DNS split, connectivity, Remote ingress, WireGuard, generated config, and DHCP leases.
- Module ownership for each check.
- Runtime target for each evidence source.
- Command hints and expected evidence.
- Criticality counts and profile-aware fallback behavior.
- Live gates that group checks into pre-apply decisions and post-apply regression checks.
- Current evidence source and next step for structured `homenet check --live`.

The command does not run probes, read command output, query live infrastructure, or include secrets. OpenWrt-only profiles do not show server-only Docker/systemd checks; they expose router-side lightweight status, OpenWrt init/filesystem, OpenWrt-local proxy, WireGuard, generated config, policy, DNS, connectivity, Remote ingress, Cloudflare provider, and DHCP evidence instead. `homenet check --live` consumes this contract for both OpenWrt + server and OpenWrt-only deployments as read-only evidence. Future apply workflows must use the pre-apply gates before source-tool changes and the post-apply regression gate after each change.

### 11.11 Artifacts

`homenet artifacts` is the apply-before contract. It consumes `homenet.metadata.v1` and emits `homenet.artifacts.v1`.

It does not render files and does not write OpenWrt, Docker, systemd, Kuma, Cloudflare, or databases. It lists what a future generator would touch:

- Artifact ID and module owner.
- Target runtime: OpenWrt, server runtime, Room AP, operator, or cloud service.
- Kind: UCI config, service config, systemd unit, Docker runtime config, generated data, generated docs, or route policy.
- Path or external surface.
- Risk level, such as `read-only`, `service-restart`, `network-disruptive`, `remote-entry-change`, or `database-write-if-applied`.
- Backup requirement.

This keeps `apply` reviewable: the operator can see concrete artifacts before any future command writes live config.

### 11.12 Bundle

`homenet bundle` writes a read-only review directory for one instance and emits `homenet.bundle.v1` in `manifest.json`.

It should include:

- `profiles.json/md`
- `quickstart.json/md`
- `module-definitions.json/md`
- `module-artifacts.json/md`
- `module-renderers.json/md`
- `module-implementations.json/md`
- `modules.json/md`
- `module-registry.json/md`
- `blueprint.json/md`
- `ownership.json/md`
- `status.json/md`
- `runbook.json/md`
- `topology.json/md`
- `incident.json/md`
- `doctor.json/md`
- `secrets.json/md`
- `inputs.json/md`
- `worksheet.json/md`
- `preflight.json/md`
- `readiness.json/md`
- `rollback.json/md`
- `evidence.json/md`
- `live-proof.json/md`
- `plan.json`
- `metadata.json`
- `artifacts.json/md`
- `apply-plan.json/md`
- `write-enablement.json/md`
- `executor-plan.json/md`
- `backup-plan.json/md`
- `backup-set.json/md`
- `backup-set-check.json/md`
- `gates.json/md`
- `change-pack.json/md`
- `change-record-check.json/md`
- `evidence-check.json/md`
- `review-output-check.json/md`
- `live-result-check.json/md`
- `deploy-plan.json/md`
- `bootstrap.json/md`
- `privacy.json/md`
- `release.json/md`
- `public-package.json/md`
- `version.json/md`
- `workspace.json/md`
- `progress.json/md`
- `render-preview.json/md`
- `config-plan.json/md`
- `rescue.json/md`
- `scripts.json/md`
- `kuma.json/md`
- `maintenance.md`
- `verify.json`
- `ci.json/md`
- `manifest.json`

The command writes only the requested output directory. It must not read live infrastructure, apply config, write OpenWrt, write Docker/systemd, mutate Kuma, call Cloudflare, or include secrets. Non-empty output directories require explicit `--force`.

### 11.13 Deploy Plan

`homenet deploy --dry-run` emits `homenet.deploy_plan.v1`. It is the end-to-end deployment workflow checklist.

It provides:

- Ordered deployment phases from profile selection through live verification.
- Commands for each phase.
- Blockers gathered from inputs, preflight, readiness, and disabled write-side apply.
- Summaries for inputs, preflight, readiness, rollback, and apply plan.

The command must require `--dry-run` in the current build. Without `--dry-run`, it must refuse to run. It must not write files, mutate OpenWrt, write Docker/systemd, mutate Kuma, call Cloudflare, or read secret values. It is higher level than `apply --dry-run`: deploy describes the workflow; apply describes the future artifact write contract.

### 11.14 Bootstrap Plan

`homenet bootstrap` emits `homenet.bootstrap.v1`. It is the first-install and adoption operating plan for an instance.

It provides:

- Ordered bootstrap phases from profile confirmation through review.
- Safe read-only commands an operator or AI can run.
- Source-tool actions that still require OpenWrt, Docker/systemd, Cloudflare, Kuma, or secret storage.
- Source-tool sequence with first check, live-write boundary, and rollback reference for each setup step.
- Explicit automation boundaries so setup does not imply write-side apply is enabled.

The command must not require live network access. It must not write files, mutate OpenWrt, write Docker/systemd, mutate Kuma, call Cloudflare, read secret values, or inspect live state. It is lower level than `quickstart` and more operator-facing than `deploy --dry-run`: quickstart teaches the workflow, bootstrap organizes the first real installation or adoption, and deploy summarizes the full release chain and blockers.

### 11.15 Privacy Audit

`homenet privacy` emits `homenet.privacy.v1`. It is the public/instance privacy and secret audit.

It provides:

- Scope selection: `public`, `instance`, or `all`.
- File count and finding count.
- Risk categories such as token, private key, subscription URL, account ID, email, phone number, and private domain.
- Findings with path, line, severity, and risk type only.

The command must not print matched values. It should skip known runtime/private storage paths such as `.env`, service data directories, runtime databases, caches, private generated configs, and binary artifacts. Public examples and generated docs should pass this audit before publishing or bundling.

### 11.16 Generated Maintenance Docs

`homenet docs` renders a Markdown maintenance guide from `homenet.metadata.v1`.

It should include:

- Operations Vocabulary with English terms and concise instance-specific meaning.
- Runtime targets.
- Networks and SSIDs.
- Device inventory.
- Capability matrix.
- Remote ingress.
- Service directory.
- Port inventory.
- Module checks and rollback surfaces.
- Source files and privacy note.

Generated docs are not another source of truth. They are a readable projection of instance metadata for humans and AI assistants. They keep common operational terms such as Gateway, DNS, Proxy, Tunnel, SSID, DHCP, VLAN, TProxy, and WireGuard in English, then explain what each term owns in the current instance.

### 11.17 Render Preview

`homenet render --dry-run` emits `homenet.render_preview.v1`. It does not write files. It explains which generated review surfaces are currently renderable, which config artifacts are rendered review artifacts, and which planned artifacts are still contract-only.

It provides:

- Renderable review surfaces such as profiles, modules, blueprint, ownership, status, plan, metadata, secrets, inputs, preflight, readiness, rollback, evidence, live-proof, artifacts, apply-plan, write-enablement, executor-plan, backup-plan, backup-set, backup-set-check, gates, change-pack, pre-change-proof, change-record-check, evidence-check, review-output-check, live-result-check, deploy-plan, bootstrap, privacy, Kuma inventory, and maintenance docs.
- Artifact-level renderability status: `renderable`, `rendered-review-artifact`, `review-fragment`, or `contract-only`.
- A clear separation between generated review outputs and future live configuration renderers.
- Privacy notes confirming that secret values are not included.

The command must require `--dry-run` in the current build. Without `--dry-run`, it must refuse to run. Future file-writing renderers must write only to explicit output directories until apply gates are implemented.

### 11.18 Config Generation Plan

`homenet generate --dry-run` emits `homenet.config_plan.v1`. It consumes `homenet.metadata.v1` and renders review-only artifacts for selected configuration domains. With an explicit `--output-dir`, it may write those review artifacts to that directory only.

It provides:

- AdGuard domestic upstream rendered review artifact for deterministic local rules, default upstream contract, source-list contract, and source-tool commands.
- AdGuard service config inventory for endpoints, ports, dependencies, and source-tool boundary without AdGuardHome.yaml values.
- Mihomo service config inventory for endpoints, ports, provider/update contract, policy intent, update units, and required secret names without provider URLs, nodes, controller secrets, or runtime cache.
- Mihomo TProxy route-policy inventory and update-unit inventory without executable firewall commands or systemd mutation.
- UCI review inventory for Gateway network/DHCP/firewall/wireless, DNS forwarding, Maintenance Wi-Fi network/wireless/firewall, and Room AP network/wireless/firewall without executable commands or Wi-Fi passwords.
- Docker Compose inventory rendered review artifact that maps declared services, owners, roles, and ports without env values.
- systemd units inventory rendered review artifact that maps repo-owned services, timers, commands, schedules, restart policy, and install targets without touching live systemd.
- Remote Access rendered review artifacts for Cloudflare Tunnel/Access, Caddy IPv6/LAN entries, WireGuard return-home endpoint, and DDNS hostnames without tokens, peer keys, certificates, or live provider writes.
- Observability runtime inventory for HomeNet Ops without image build caches, env values, or runtime state.
- Kuma import review inventory for monitor candidate counts, auto/manual importability, DB diff prerequisites, backup gates, and guarded apply policy without reading the Kuma database.
- Smart Home service config inventories for Home Assistant, Mosquitto, and Zigbee2MQTT that list endpoints, ports, dependencies, and secret names without service config values or runtime storage.
- Renderer readiness for each artifact, including `deployable: false`, gate-level promotion checklist, and blocker evidence.

The command must require `--dry-run` in the current build. Without `--dry-run`, it must refuse to run. Without `--output-dir`, it must not write files. With `--output-dir`, it may write only review artifacts and a manifest under that explicit directory, must not use live service paths, and must require `--force` for non-empty directories. The output is not a complete deployable config and must not be applied directly. `rendered-review-artifact` means a deterministic renderer exists for its declared review scope, but write-side apply is still disabled. `review-fragment` remains available for future partial artifacts where the project can show intent but not a complete review scope. `promotion_checklist` is the review contract for each artifact: renderer completeness, write-side enablement, backup/rollback, secret resolution, and network-change confirmation must be explicit before it can become deployable.

### 11.19 Rescue

`homenet rescue` emits `homenet.rescue.v1`. It consumes `homenet.metadata.v1` and turns declared networks, Wi-Fi, service entries, remote ingress, and runtime targets into a practical maintenance map.

It provides:

- Maintenance Wi-Fi and maintenance network purpose.
- Local IP entries for HomeNet Ops, OpenWrt LuCI/SSH, Pi SSH, room AP, Kuma, Mihomo, AdGuard, and WireGuard when declared.
- Remote entry points with target and status source.
- SSH targets and command hints without embedding keys or passwords.
- Common failure modes for DNS/proxy problems, Pi/server runtime problems, gateway/Wi-Fi problems, and outside-home access problems.
- Operator rules that prefer declared IP entries when DNS, proxy, or tunnels are suspect.

The command must not read Wi-Fi passwords, SSH keys, tokens, session files, live router config, Docker state, Cloudflare state, or Kuma databases. It is a low-dependency orientation surface for humans and AI assistants during normal maintenance and break-fix work.

### 11.20 Runbook

`homenet runbook` emits `homenet.runbook.v1`. It consumes the instance, metadata, rescue guide, ownership map, status summary, evidence plan, and scripts inventory to produce a scenario-oriented operations manual.

It provides:

- Common scenarios such as slow/intermittent network, Wi-Fi connected without internet, DNS/Proxy routing mistakes, server runtime outages, remote access failures, room AP/roaming issues, missing IoT devices, noisy Kuma monitors, and AI-assisted maintenance access.
- Symptoms, first entries, source tools, safe read-only commands, check order, and explicit "do not" rules for each scenario.
- A shared observe-enter-isolate-confirm-change-verify phase model.
- Source-of-truth boundaries so the maintainer knows whether to inspect OpenWrt, AdGuard, Mihomo, Cloudflare, WireGuard, Kuma, server runtime, or HomeNet.

The command must stay read-only. It must not query live infrastructure, write files, mutate source tools, or print secrets. Its purpose is to make a maintainer's first 15 minutes predictable and to prevent blind changes.

### 11.21 Topology

`homenet topology` emits `homenet.topology.v1`. It consumes `homenet.metadata.v1` and turns the declared instance into a graph of nodes, edges, service placement, remote ingress, and traffic paths.

It provides:

- Runtime nodes for Internet/WAN, OpenWrt Gateway, server runtime, and optional Room AP.
- Network nodes for LAN, IoT, Guest, Maintenance, modem, or any declared network.
- Wi-Fi/SSID nodes and broadcast edges from Gateway or APs.
- Device nodes and declared network attachment edges.
- Service nodes, runtime ownership edges, and remote ingress edges.
- Traffic paths for home LAN, domestic direct, foreign proxy, explicit proxy, remote web, WireGuard return-home, Maintenance, Room AP coverage, and IoT/smart-home flows.

The command is a declared topology, not live evidence. It must not read router state, Docker state, Cloudflare state, passwords, tokens, keys, or runtime databases. `homenet status --live` and `homenet check --live` prove whether the current home matches the topology.

### 11.22 Incident

`homenet incident` emits `homenet.incident.v1`. It is the CLI version of the Ops first screen: one page for current mode, the first five minutes, decision flow, recovery matrix, triage domains, maintenance path, safe entries, active issues, and next commands.

It consumes existing status, doctor, rescue, runbook, and topology surfaces instead of creating another source of truth. Offline mode is the default and explains the intended troubleshooting order. `decision_flow` orders the first troubleshooting questions from maintenance path through Gateway/WAN, Wi-Fi/Room AP, DNS/Proxy, server runtime, and remote ingress. `recovery_matrix` maps common symptoms to the first probe, follow-up evidence, owning source tool, and what not to start with. `--live` reads the same read-only evidence family as `doctor --live` so the page can classify the current situation as normal, degraded, or an active incident.

The command is read-only. It does not write files, mutate source tools, restart services, call provider write APIs, or print passwords, tokens, keys, cookies, sessions, Wi-Fi secrets, or proxy subscriptions.

### 11.23 Doctor

`homenet doctor` emits `homenet.doctor.v1`. It consumes status, topology, runbook, ownership, and optional live evidence to produce a diagnostic triage surface.

It provides:

- Overall health: `unknown-offline`, `healthy`, `degraded`, or `action-required`.
- Issue grouping by domain and level.
- Live warning/failure classification for Wi-Fi, Remote Access, Proxy Policy, Cloudflare Provider, Device Presence, and general findings.
- Likely cause, first actions, source tools, related runbook scenario, and related topology path for each issue.
- Source-of-truth boundaries so the operator knows where a real change belongs.

The command is read-only. Offline mode does not read live infrastructure and says so explicitly. `--live` reads the same evidence family as `status --live` and `check --live`, but still does not write files, mutate OpenWrt, restart services, change Kuma, call Cloudflare write APIs, or print secrets. It is triage, not automatic repair.

### 11.24 Scripts

`homenet scripts` emits `homenet.scripts.v1`. It scans repository-owned operational scripts and runtime task definitions, then maps them to HomeNet modules.

It provides:

- Script path, kind, runtime target, module owner, status, purpose, and disposition.
- Summary by module, script kind, and status.
- Explicit classification for maintenance/source-tool helper scripts that still exist as files.
- A rule that long-lived scripts should become module-owned operations, generated artifacts, runtime units, or checks instead of hidden one-off control paths.

The command must skip generated state, env files, databases, service-owned runtime data, and private values. It must not execute scripts or query live infrastructure. Its purpose is to keep script sprawl visible while the project moves toward declared modules and generated artifacts.

### 11.25 Kuma

`homenet kuma` is a read-only Uptime Kuma inventory export. It consumes `homenet.metadata.v1` and emits `homenet.kuma_inventory.v1`.

It provides:

- Monitor candidates grouped by Remote Access, Network Core, Home Core, HomeNet Core, and Other.
- Monitor type and target.
- Scope, source, recommended interval, and alert intent.
- Whether a candidate is safe for automatic import or should stay manual.

The inventory and diff commands must not write to Kuma's database. `homenet kuma --diff-db --import-plan --apply-db` is the guarded write workflow: without `--confirm-apply APPLY-KUMA` it returns `homenet.kuma_apply_result.v1` as a dry-run; with confirmation it creates a timestamped database backup first, then applies only selected safe actions. It never deletes extra monitors and treats operator-owned monitors as out of scope unless explicitly selected by a future adoption workflow.

### 11.26 Apply

`homenet apply --dry-run` emits `homenet.apply_plan.v1`. It consumes preflight, readiness, rollback, artifacts, evidence, and metadata, then produces the write-side contract without writing live state. Non-dry-run `homenet apply` must emit `homenet.apply_result.v1` with `status=refused`, `applied=false`, and `writes_live_config=false` until write-side apply exists. `--batch <id>` scopes the refusal result to selected future execution batches and emits batch packages for those selections. `--confirm-apply APPLY-HOMENET` is accepted only as an explicit audit marker in the current build; neither may enable writes.

It provides:

- Preflight, backup, render, apply, and verify phases.
- Apply gates for privacy, secret resolution, review renderer availability, backup capture, live verification before/after, operator confirmation, source-tool ownership, and write-side enablement.
- Deterministic artifact order.
- Execution plan entries that map every artifact to a future writer, target, risk, required gates, blocked gates, current disabled mode, and disabled reason.
- Writer contracts grouped by source-tool owner. Each contract declares owner, source tool, write surface, artifact count, targets, risks, required gates, blocked gates, disabled mode, and promotion requirements.
- Module executor readiness gates. Each future writer declares required gates, optional gates, and the promotion rule that must be satisfied before `supports_write` can ever become true.
- Write enablement grouped by writer. It must summarize whether each writer is eligible, which gates still block it, which implementation steps are missing, which proof is required, and why global write-side apply remains disabled.
- Executor capabilities grouped by writer. Each capability declares implementation status, supported dry-run/review operations, `supports_write=false`, disabled reason, and implementation prerequisites.
- Execution batches grouped by risk order. Each batch declares order, intent, artifacts, writers, required/blocked gates, pre-checks, post-checks, failure action, and disabled mode.
- Apply readiness derived from gates and batches. It must expose global status, per-batch status, review-only batches, blocked batches, required confirmations, and `eligible_for_write=false` while write-side apply is disabled.
- Optional `homenet.gate_evidence.v1` input for dry-run gate simulation. It may mark prerequisite gates as pass and recalculate artifact `blocked_gates`, but it must never enable `write-side-enabled`.
- Backup plan derived from artifacts that require backup, including capture, restore, and verify plans without executing them.
- Blockers from preflight and readiness.
- Warnings from preflight, readiness, and rollback.
- Verification commands to run before and after any future write-side apply.

The command must not write live state in the current build. With `--dry-run`, it emits the full apply plan. Without `--dry-run`, it must return a structured refusal result instead of a one-line error unless the operator explicitly requests the local review-only writer. Batch selection and a matching confirmation token may be recorded in that refusal result. Batch packages must include selected artifacts, execution items, backup items, writer contracts, executor capabilities, pre/post checks, and failure action without executing any of them. It must not execute backup commands.

The only enabled writers in the current build are reviewable local-output writers. `homenet apply --batch config-review --confirm-apply APPLY-HOMENET --review-output-dir <dir>` may write every rendered config review artifact plus `manifest.json` under the explicit local output directory. `homenet apply --batch review-only --confirm-apply APPLY-HOMENET --review-output-dir <dir>` may write `maintenance.md`, `verify.json`, and `manifest.json` under the explicit local output directory. `homenet apply --batch server-runtime-review --confirm-apply APPLY-HOMENET --review-output-dir <dir>` may write `metadata.json`, `kuma.json`, and `manifest.json` under the explicit local output directory. These results may set `status=review-applied`, `applied=true`, and `writes_files=true`, but they must keep `writes_live_config=false`. They must refuse unknown batches, multiple batches, non-reviewable batches, missing confirmation, and non-empty output directories unless `--force` is set. `homenet review-output-check --dir <dir>` emits `homenet.review_output_check.v1` and validates the manifest schema, batch id, artifact list, expected file names, file presence, and `writes_live_config=false` without printing file contents. Reviewable writers and output checks must not write OpenWrt, Docker/systemd, Cloudflare, Kuma databases, service-native config, backups, or live state. Live write-side apply remains disabled until executor readiness gates, backups, secret scoping, generated artifact review, operator confirmation, source-tool ownership, and live verification gates are explicit and executable.

`homenet exec-plan` emits `homenet.executor_plan.v1`. It consumes the same apply plan and selected batch packages, then normalizes them into a future runner contract: ordered stages, pre-checks, backup items, operations, post-checks, writer contracts, executor capabilities, hard blockers, and promotion requirements. It is read-only in the current build: `executes_commands=false`, `writes_live_config=false`, and `write_enabled=false`. It must not run backups, run checks, restart services, write source tools, or mutate OpenWrt, Docker/systemd, Kuma, Cloudflare, or service databases. With `--execute`, it must emit `homenet.executor_result.v1` as a structured refusal with `executed=false`, `executes_commands=false`, `writes_files=false`, and `writes_live_config=false`; `--confirm-execute EXECUTE-HOMENET` may record explicit intent but must not enable execution. Its purpose is to make the future guarded apply runner input stable before any writer is enabled.

`homenet backup-plan` emits `homenet.backup_plan.v1`. It consumes the same apply plan and selected batch packages, then isolates backup capture into its own future runner contract: backup set rules, ordered backup items, target/method/module counts, method capabilities, capture commands, restore plans, verify commands, blockers, and promotion requirements. `homenet backup-set` emits the matching `homenet.backup_set.v1` review surface for the future backup set manifest: it lists required files, expected capture paths, per-item capture/restore/verify proof, and forbidden storage locations without captured files. With `--init-dir <dir>`, `backup-set` may initialize a local backup-set directory outside the git worktree by writing only `manifest.json` and `backup-plan.json`, then validating the manifest with `backup-set-check`; it must not create captures, copy live files, run SSH, read databases, execute restore, verify backup contents, or mark anything captured. `homenet backup-set-check` emits `homenet.backup_set_check.v1` for a saved `homenet.backup_set_manifest.v1`; it validates schema, required fields, backup root placement, relative capture paths, path traversal, duplicate captures, and captured/verified/restored state consistency without reading captured file contents. Method capabilities must describe `server-file-copy`, `openwrt-ssh`, `database-copy`, and generic source-tool export support, including disabled reasons and implementation prerequisites. It is read-only in the current build except for explicit backup-set initialization files: `executes_commands=false`, `writes_live_config=false`, `capture_enabled=false`, `restore_enabled=false`, and `verify_enabled=false`. With `--capture`, `--restore`, or `--verify`, it must emit `homenet.backup_result.v1` as a structured refusal with `captured=false`, `restored=false`, `verified=false`, `executes_commands=false`, `writes_files=false`, and `writes_live_config=false`; matching confirmation tokens may record explicit intent but must not enable capture, restore, or verify. Its purpose is to make backup capture, restore, and verification auditable before any write-side apply implementation can depend on them.

`homenet gates` emits `homenet.gates.v1`. It is the pre-change gate dashboard for operators and AI assistants.

It aggregates:

- Apply gates from `homenet apply --dry-run`.
- Live gates from `homenet evidence`.
- Blockers and warnings from `preflight`, `readiness`, and the apply contract.
- Status counts, required blocked gates, required secret count, and next actions.

`homenet live-proof` emits `homenet.live_proof.v1` as a standalone read-only proof-record contract derived from the evidence plan. It defines what must be saved before and after a future guarded write, which fields are summaries only, and which values are forbidden from proof records.

`homenet evidence-check` emits `homenet.gate_evidence_check.v1`. It validates a `homenet.gate_evidence.v1` file without printing evidence values. It must report schema, unknown sections, unknown fields, invalid boolean/string/list/object types, multi-line values, and secret-like field names by path only. Evidence files with errors must not be used to pass gates in `apply`, `exec-plan`, `backup-plan`, `backup-set`, `gates`, or `change-pack`; the commands may still include the error paths and warning counts so operators can fix the evidence file. `--template` emits the same safe placeholder evidence template used by `gates` and `apply`.

`homenet live-result-check` emits `homenet.live_result_check.v1`. It validates a saved `homenet verify --live --json` or `homenet ci --live --format json` result before that result is referenced as live proof. It checks schema, `live=true`, `ok=true`, failure counts, and the presence of live checked rows, but it must not re-run live probes, print raw findings, print command output, or write files.

`homenet change-record` emits `homenet.change_record_init.v1`. It initializes a standard change record directory from operator-provided proof files: gate evidence, pre-apply live result, backup-set manifest, executor plan, and optional post-apply live result. The output directory must be outside the HomeNet git worktree. The command may copy those source files into standard names and then run the same validation as `change-record-check`, but it must not generate proof, run live probes, read capture contents, call providers, mutate source tools, or touch live configuration.

`homenet pre-change-proof` emits `homenet.pre_change_proof.v1`. It assembles a local pre-change proof directory outside the HomeNet git worktree from operator-provided gate evidence and pre-apply live result files. The command may generate `config-review/` review output, initialize a `backup-set/` manifest skeleton, write `executor-plan.json`, write `change-pack.json`, copy the provided proof files into standard change record names, and write a local `manifest.json`. It must validate the gate evidence, live result, review output, backup-set manifest, and final change record before returning success. It must not run live probes, create backup captures, read capture contents, SSH to devices, call provider APIs, restart services, mutate source tools, or touch live configuration. Its purpose is to make the whole pre-change boundary reviewable and reproducible before any future guarded write.

`homenet change-record-check` emits `homenet.change_record_check.v1`. It validates a saved pre-change proof directory before that directory is used as guarded-apply evidence. The directory must contain `gate-evidence.json`, `pre-apply-live.json`, `backup-set-manifest.json`, and `executor-plan.json`; `post-apply-live.json` is optional before a future guarded write and expected after one. The command delegates each record to the matching schema checker, verifies that the executor plan is still read-only, and reports only record ids, file paths, statuses, and counts. It must not run probes, read backup capture contents, print proof values, call providers, mutate source tools, write files, or touch live configuration.

Commands that accept `--evidence-file` for gate simulation may also accept `--change-record-dir`. When a change record directory is provided, the command must first run the same directory validation and may only use the contained `gate-evidence.json` if the full change record is valid. Invalid directories must not pass any gates; they may add structured warnings so the operator can repair the proof. A change record can reduce missing proof in `gates`, `apply --dry-run`, `exec-plan`, `backup-plan`, `backup-set`, and `change-pack`, but it must never enable write-side apply while `write-side-enabled` remains blocked.

`homenet change-pack` emits `homenet.change_pack.v1`. It is the pre-change packet for a selected instance and optional batch selection. It must aggregate batch readiness, blocked gates, writer proof requirements, required evidence records, the backup set manifest template, and safety boundaries from the existing apply, gates, executor, backup, backup-set, write-enablement, and live-proof surfaces. It is read-only in the current build: `executes_commands=false`, `writes_files=false`, and `writes_live_config=false`. It must not create backup directories, copy files, run SSH, call provider APIs, restart services, probe live systems, or mutate source tools. Its purpose is to give humans and AI assistants one stable entry point before any future guarded write while preserving source-tool ownership.

It may also read an optional `homenet.gate_evidence.v1` JSON file. That file is a proof summary, not a log archive. It may contain only booleans, timestamps, and source labels for these sections:

- `secrets.confirmed`
- `backups.captured`
- `live.pre_apply_passed`
- `live.post_apply_passed`
- `operator.confirmed`
- `source_tools.reviewed`

`source_tools.reviewed` is the coarse source-tool gate flag. Evidence files should also keep `source_tools.writer_reviews`, with one row per future writer such as OpenWrt, room AP, server runtime, and review bundle. Every required writer row must show the owner, source tool, write surface, review timestamp, and `reviewed=true` before `source-tool-ownership` can pass.

The command is read-only and does not execute live checks. It must not write files, mutate OpenWrt, write Docker/systemd, mutate Kuma, call Cloudflare, read secret values, or print secret values. Evidence files must not contain command output, passwords, tokens, private keys, cookies, sessions, proxy subscription URLs, or service-native config values. Its purpose is to answer whether a planned change is allowed to proceed and what condition must be satisfied first. Evidence can clear prerequisite gates, but it must not clear `write-side-enabled` while write-side apply is disabled in code.

Future write-side apply must use this safe order:

1. Create backups.
2. Deploy non-network services.
3. Deploy DNS/proxy services.
4. Apply OpenWrt config.
5. Verify local access.
6. Verify WAN, DNS, proxy, and maintenance path.

### 11.27 Check

Runs read-only checks:

- WAN and IPv6.
- DNS domestic and foreign behavior.
- Proxy route behavior.
- Remote access endpoints.
- HomeNet and critical services.
- Static DHCP and expected devices.
- Maintenance Wi-Fi reachability.

### 11.28 Restore

Restores the last known safe config for:

- OpenWrt network/firewall/wireless/dhcp.
- Mihomo config.
- AdGuard config.
- Docker compose services.

Rollback should not depend on external internet.

## 12. HomeNet Information Architecture

HomeNet should be the daily entry for the deployment instance.

Primary pages:

- Overview: system status, most used entries, attention items.
- Topology: real home topology generated from instance and live data.
- Services: service directory and port inventory.
- Network: devices, route groups, DNS, traffic evidence.
- Access: remote entry, WireGuard, Cloudflare, Maintenance Wi-Fi, presence.
- Fix: symptom-based diagnostics using real module names.
- Health: read-only checks and recent failures.

Tone:

- Keep English module names.
- Use concise Chinese role descriptions in Chinese deployments.
- Avoid hiding technical terms.
- Avoid unexplained walls of raw metrics.

Example:

```text
Mihomo Proxy
规则代理核心。AI / foreign traffic goes through AI-NODES; domestic IPs stay DIRECT.
```

## 13. Implementation Boundaries

The most important implementation rule is avoiding unclear ownership.

### 13.1 HomeNet Ops vs Source Tools

HomeNet Ops should:

- Show the daily status in one place.
- Explain topology and paths.
- Link local and remote service entries.
- Show which source tool owns each fact.
- Trigger safe read-only checks.
- Eventually trigger carefully scoped actions that have explicit rollback.

HomeNet Ops should not:

- Become another full router admin panel.
- Duplicate Mihomo Dashboard proxy group controls.
- Duplicate AdGuard query management.
- Duplicate Home Assistant device control.
- Hide that a problem comes from OpenWrt, DNS, Proxy, Tunnel, or upstream WAN.

### 13.2 Uptime Kuma vs HomeNet

Uptime Kuma owns alerting and uptime history.

HomeNet owns explanation and correlation:

- Kuma says `Home Assistant is DOWN`.
- HomeNet says whether Pi, Docker, Caddy, Cloudflare Tunnel, LAN entry, and WAN entry are healthy around the same time.

### 13.3 Cloudflare vs WireGuard

Cloudflare Tunnel / Access is for selected HTTPS entries.

WireGuard is for LAN-level return path and maintenance. It is the right tool when the operator needs to reach `192.168.x.x`, SSH, LuCI, or non-HTTPS local services.

### 13.4 Maintenance Wi-Fi

Maintenance Wi-Fi is not a performance network. It is a maintenance path:

- Keep it simple.
- Keep it independent from transparent proxy behavior.
- Allow enough LAN reachability to reach Pi and recovery entries.
- Avoid expanding it into a full privileged daily network unless the instance declares that intentionally.

## 14. Private Real-Home Instance

A real home deployment can map naturally to the standard OpenWrt + server-runtime profile:

- OpenWrt Gateway owns WAN, DHCP, Firewall, Wi-Fi, VLAN/network boundaries, and optional TProxy handoff.
- Server runtime can be Pi, mini PC, NAS, or another always-on host.
- Room AP can be an OpenWrt relay/AP, wired AP, mesh node, or omitted.
- Main LAN, IoT Network, Guest Network, and Maintenance Wi-Fi are declared by the instance.
- DNS can be AdGuard on server runtime or dnsmasq/mosdns on OpenWrt.
- Proxy can be Mihomo on server runtime, OpenWrt, or another declared runtime.
- Remote access: WireGuard, Caddy, Cloudflare Tunnel
- Observability: HomeNet Ops and Uptime Kuma
- Smart home: Home Assistant, Mosquitto, Zigbee2MQTT, go2rtc

Instance-specific items:

- SSID names.
- Private production domains from a deployment instance.
- Cloudflare Access setup.
- Proxy provider subscriptions.
- Fixed devices and owners.
- Home Assistant dashboards and devices.
- Private service credentials.

These should move into private instance files or documented local overrides over time.

## 15. First Implementation Milestone

The first milestone should not attempt full auto-deployment. It should create a solid foundation:

1. Define schema files for `site.yaml`, `devices.yaml`, and `services.yaml`.
2. Create public example instances and a private real-home instance draft with secrets omitted.
3. Refactor HomeNet Ops to read service/network metadata from the instance files instead of hardcoding every service.
4. Add `homenet check` as a read-only checker that runs current health checks against an instance.
5. Add `homenet plan` that reports intended module placement without applying changes.
6. Keep existing live network untouched until the generated metadata matches current reality.

Success criteria:

- A new maintainer can read the design and understand what the project provides.
- The current home can be described as one instance of the model.
- No secret is added to git or printed.
- Running checks proves the instance metadata matches live network facts.
- HomeNet continues to work for the current deployment.

Initial files created for this milestone:

- `schemas/site.schema.yaml`
- `schemas/devices.schema.yaml`
- `schemas/services.schema.yaml`
- `instances/example-openwrt-pi/site.yaml`
- `instances/example-openwrt-pi/devices.yaml`
- `instances/example-openwrt-pi/services.yaml`
- `instances/example-openwrt-pi/README.md`
- `instances/example-openwrt-only/site.yaml`
- `instances/example-openwrt-only/devices.yaml`
- `instances/example-openwrt-only/services.yaml`
- `instances/example-openwrt-only/README.md`
- private real-home `site.yaml`, `devices.yaml`, and `services.yaml` outside the public package
- `tools/homenet.py`
- `homenet`

Current status:

- Instance schemas and public example instance drafts exist.
- `homenet profiles` exports `homenet.profiles.v1` as the deployment-shape catalog. It lists `openwrt-pi`, `openwrt-mini-pc`, and `openwrt-only` hardware assumptions, required inputs, tradeoffs, examples, scaffold commands, and capability matrix without reading live infrastructure.
- `homenet quickstart` exports `homenet.quickstart.v1` as the first deployment guide. It presents a short operator summary for first deployment, daily use, incident response, and public/private boundaries before the staged workflow. It orders profile selection, instance scaffold, inputs, secrets/preflight, CI/bundle review, and live verify without reading secret values or writing live state. Deploy/rollback/apply/render/gates/evidence/generate are Advanced Review surfaces for automation and live-change preparation.
- `homenet check` exists and validates the instance. It now applies the lightweight schema files before semantic checks, covering required fields, scalar types, enums, CIDR/IP/URL/MAC formats, list items, and pattern fields.
- `homenet check --live` consumes `homenet.evidence.v1`. For the OpenWrt + server profile it checks HomeNet API, local systemd units, Docker containers, generated config files, Pi TProxy, OpenWrt policy, DNS split, connectivity, Remote ingress, Cloudflare provider state, WireGuard state, and OpenWrt DHCP leases without writing live state. For the OpenWrt-only profile it checks router-side lightweight status, OpenWrt init/filesystem, OpenWrt-local proxy, WireGuard, generated config, policy, DNS, connectivity, Remote ingress, Cloudflare provider state, and DHCP evidence.
- `homenet examples` runs a read-only smoke test across public example instances. It validates check, blueprint, plan, metadata, secrets, inputs, preflight, readiness, rollback, evidence, artifacts, deploy plan, apply plan, privacy audit, render preview, config plan, rescue guide, scripts inventory, capability matrix, and Kuma inventory generation without touching live infrastructure.
- `homenet init` scaffolds a new editable instance from the public OpenWrt + server or OpenWrt-only example templates, then writes an instance-specific README with the correct path, profile, first-pass commands, verify/package commands, Advanced Review commands, and secret-handling rules. It does not write secrets and refuses overwrite unless `--force` is explicit.
- `homenet verify` is the local read-only verification gate. It checks public examples plus the selected deployment instance, validates generated blueprint, secrets, inputs, preflight, readiness, rollback, evidence, artifacts, deploy plan, apply plan, privacy audit, render preview, config plan, rescue guide, scripts inventory, docs, Kuma inventory, incident decision/recovery counts, and quickstart operator-summary sections, and only reads live OpenWrt/Docker/HomeNet evidence when `--live` is explicitly set.
- `homenet ci` exports `homenet.ci.v1` as the aggregate read-only gate. It combines public privacy, instance privacy, public examples, module definition/artifact/renderer/implementation contract checks, selected instance verify, incident-surface coverage, quickstart-surface coverage, bootstrap-sequence coverage, private-instance-boundary coverage, render preview, and bundle smoke; `--live` only affects the selected instance verify step.
- `homenet blueprint` exports `homenet.blueprint.v1` as the top-level product/instance contract. It answers what the project solves, what it provides, what it does not promise, where operational evidence lives, and which capabilities are active or fallback for the current instance.
- `homenet plan` exists as a no-change module report for the current instance. It lists Placement, Inputs, Outputs, Checks, and Rollback for Gateway, DNS, Proxy, Remote Access, Observability, Smart Home, Maintenance Wi-Fi, Server Runtime, and Room AP.
- `homenet plan` also exports a runtime capability matrix. It records each module's required/optional status, supported runtime options, current placement, OpenWrt-only fallback, and with-server capability.
- `homenet modules` also exports Module Decisions so a new deployer can see which modules are baseline, recommended, optional, or capacity/coverage add-ons, and what happens when each is disabled.
- `homenet ownership` exports `homenet.ownership.v1` as the source-of-truth and write-boundary map. It records ownership areas, networks, Wi-Fi, services, modules, artifacts, future writers, source tools, HomeNet roles, write rules, and the `source_tools.reviewed` evidence key without reading live state or secrets.
- HomeNet Ops reads service, port, network, Wi-Fi, and device metadata from the selected instance directory, then overlays live probe status.
- HomeNet Ops consumes `homenet.plan.v1` from the same CLI planner and displays module-level Placement, Checks, and Rollback summaries in Topology and Fix.
- Ops copy keeps operational terms such as Gateway, DNS, Proxy, Tunnel, SSID, DHCP, VLAN, TProxy, WireGuard, Checks, and Rollback, with concise Chinese context where needed.
- HomeNet Ops service and port probes are generated from instance `services.yaml`; Ops-local overrides are limited to probe path, localhost mapping, and key aliases.
- `homenet metadata` exports `homenet.metadata.v1` with service directory, port inventory, remote ingress, Kuma monitor candidates, devices, networks, Wi-Fi, runtime targets, module plan, and capability matrix.
- `homenet secrets` exports `homenet.secrets.v1` as the secret prerequisite contract. It lists expected secret names, scope, required/optional status, module usage, purpose, and storage hints without reading or printing values; `--template` prints placeholder env lines for a local secret store without writing files.
- `homenet inputs` exports `homenet.inputs.v1` as the deployment input checklist. It lists required profile inputs, instance files, runtime targets, networks, Wi-Fi, declared modules, module placement, secret names, and auto defaults without reading secret values or live state.
- `homenet worksheet` exports `homenet.worksheet.v1` as the operator deployment worklist. It groups inputs, secret names, preflight, readiness, and review gates into actionable sections without reading secret values or writing live state.
- `homenet preflight` exports `homenet.preflight.v1` as the local operator prerequisite report. It checks command presence, Python dependencies, required secret name presence, accepted command aliases, and service-native secret confirmations without printing secret values or touching live infrastructure.
- `homenet readiness` exports `homenet.readiness.v1` as the offline review/apply gate. It reports review blockers, apply blockers, warnings, and next actions without reading secret values or live infrastructure.
- `homenet rollback` exports `homenet.rollback.v1` as the read-only backup and rollback contract. It lists module rollback sources, inferred backup sources, backup capture/restore/verify plans, recovery order, and high-risk artifact counts without executing backups, restoring, or writing live state.
- `homenet evidence` exports `homenet.evidence.v1` as the read-only live evidence plan. It maps module-owned live checks to module-owned evidence sources and adapts the plan for OpenWrt-only versus OpenWrt + server profiles without executing probes. It also exports live gates for maintenance entry, server runtime core, gateway policy core, DNS/proxy connectivity, remote return-home, device presence, and post-apply regression. Its adoption status is implemented for both OpenWrt + server and OpenWrt-only evidence sets, including read-only Cloudflare provider checks; run `homenet check --live` directly.
- `homenet artifacts` exports `homenet.artifacts.v1` as the apply-before contract. It lists planned OpenWrt UCI, service config, systemd, Docker, Kuma, docs, and route-policy artifacts with owner, target, risk, and backup requirement, without writing files or devices.
- `homenet deploy --dry-run` exports `homenet.deploy_plan.v1` as the end-to-end deployment workflow checklist. It orders profile selection, instance inputs, secrets, preflight, bundle review, rollback, config review, future apply contract, and live verify, and summarizes config review artifacts plus backup capture/restore/verify plans without writing files or live state.
- `homenet bootstrap` exports `homenet.bootstrap.v1` as the first-install and adoption operating plan. It lists phases, safe commands, source-tool actions, source-tool sequence, secret prerequisites, rollback/apply contracts, and live verify order without writing files or live state.
- `homenet privacy` exports `homenet.privacy.v1` as the public/instance privacy audit. It reports only file path, line number, severity, and risk type, never matched secret values.
- `homenet release` exports `homenet.release.v1` as the public release boundary report. It separates public core roots from private deployment/runtime roots and states that the whole live worktree is not publishable.
- `homenet publish-audit` exports `homenet.public_publish_audit.v1` as the final public release readiness report. It aggregates release boundary, privacy counts, package evidence, public repo evidence, optional full publish-check results, remaining warnings, and next actions without printing secret values or writing live configuration.
- `homenet release-candidate` exports `homenet.public_release_candidate.v1` as the local publish-ready review before a real public remote exists. It writes only the requested package/repo candidate directories, initializes a local public git repo, aggregates package/repo/audit evidence, and never adds a remote, pushes, or writes live network configuration.
- `homenet repo-publish` exports `homenet.public_repo_publish.v1` as the guarded final public repo push surface. It refuses inline-credential remotes, redacts remote URLs in reports, runs a lightweight publish audit in plan mode, and requires `--confirm-push PUSH-HOMENET-PUBLIC` before running the full publish check, adding/updating `origin`, or running `git push`.
- `PUBLISHING.md` is the short human/AI review for public release. It states the current publishing state, local release-candidate command, final checks, guarded publish command, and paths that must stay private.
- `.github/workflows/ci.yml` is part of the public package. It runs public privacy, example CI, package manifest, package check, and package smoke on push and pull request without repository secrets.
- `homenet version` exports `homenet.version.v1` as the version and workspace ownership report. It records the HomeNet core version, root git state, sibling project git state, private instance profile, and release-boundary summary without reading secret values or live infrastructure.
- `homenet workspace` exports `homenet.workspace.v1` as the mixed-workspace boundary report. It records repository ownership, publish scopes, boundary checks, and Private Instance Boundary so a real-home instance can later be separated from runtime directories without changing live network state.
- `homenet status` exports `homenet.status.v1` as the diagnostic-first daily operator summary. It includes `homenet.diagnostic_surface.v1` with fault domains, plain descriptions, first probes, follow-up probes, source-tool owners, linked services, paired remote entries, and safe next actions before the inventory sections. In live mode, each warning/failure finding is classified into one or more diagnostic domains and exposed through `domain_counts`, `classified_findings`, and per-domain `live_evidence`. It also combines Daily Entries, Runtime Targets, Networks/Wi-Fi, Module State, Remote Ingress, maintenance paths, and optional read-only live findings without writing files or live configuration.
- `homenet apply --dry-run` exports `homenet.apply_plan.v1` as the write-side contract preview. It orders artifacts, lists execution-plan writers, emits writer/source-tool contracts, executor capabilities, disabled execution batches, and apply readiness with required/blocked gates, lists backup capture/restore/verify plans, carries preflight/readiness blockers, and accepts optional boolean-only gate evidence for simulation. Non-dry-run `homenet apply` exports `homenet.apply_result.v1` as a structured refusal result with no writes in the current build.
- `homenet write-enablement` exports `homenet.write_enablement.v1` as the per-writer eligibility surface. It reads the same optional gate evidence or validated change record as apply dry-run, then reports each writer's blocked gates, missing implementation, proof requirements, and hard blockers without enabling writes.
- `homenet exec-plan` exports `homenet.executor_plan.v1` as the future runner contract. It converts selected apply batches into ordered stages with pre-checks, backup items, operations, post-checks, writer contracts, executor capabilities, hard blockers, and promotion requirements while keeping `executes_commands=false`, `writes_live_config=false`, and `write_enabled=false`. `--execute` exports `homenet.executor_result.v1` as a structured refusal and does not run operations even with a matching confirmation token.
- `homenet backup-plan` exports `homenet.backup_plan.v1` as the future backup capture/restore/verify contract. It converts selected apply batches into backup-set rules and ordered capture/restore/verify items while keeping `executes_commands=false`, `writes_live_config=false`, `capture_enabled=false`, `restore_enabled=false`, and `verify_enabled=false`. `homenet backup-set-check` validates a saved backup set manifest without reading captured backup contents. `--capture`, `--restore`, or `--verify` exports `homenet.backup_result.v1` as a structured refusal and does not execute capture, restore, or verification even with a matching confirmation token.
- `homenet gates` exports `homenet.gates.v1` as the pre-change gate dashboard. It aggregates apply gates, live gates, blockers, warnings, status counts, and next actions without executing probes or reading secret values. `--template` prints a safe `homenet.gate_evidence.v1` placeholder, and `--evidence-file` reads a boolean-only proof summary that can clear prerequisite gates while leaving write-side apply disabled.
- `homenet pre-change-proof` exports `homenet.pre_change_proof.v1` when assembling a proof directory, while bundle/render exports `homenet.pre_change_proof_contract.v1` as the read-only contract surface. The contract lists required proof records, generated files, validation commands, and forbidden live actions without requiring or creating actual proof records.
- `homenet render --dry-run` exports `homenet.render_preview.v1` as the generation preview. It lists renderable review surfaces, rendered review artifacts, review fragments, and contract-only planned artifacts without writing files.
- `homenet generate --dry-run` exports `homenet.config_plan.v1` as the review-only config generation plan. It renders AdGuard, Mihomo, OpenWrt/Gateway, Maintenance Wi-Fi, Room AP, Docker Compose, systemd, Remote Access, Observability, Kuma import, and Smart Home review artifacts without including secret values, can optionally write only review artifacts to an explicit output directory, and marks them as non-deployable with gate-level promotion checklists.
- `homenet rescue` exports `homenet.rescue.v1` as the maintenance entry map. It lists Maintenance Wi-Fi, local IP entries, remote entries, SSH targets, and common failure modes without reading or printing secrets.
- `homenet runbook` exports `homenet.runbook.v1` as the scenario-oriented operations manual. It lists symptoms, first entries, source tools, safe commands, check order, and high-risk actions to avoid without reading live state or secrets.
- `homenet topology` exports `homenet.topology.v1` as the declared network graph. It lists nodes, edges, service placement, remote ingress, and traffic paths without reading live state or secrets.
- `homenet incident` exports `homenet.incident.v1` as the incident workflow. It aggregates status, doctor, rescue, runbook, and topology into current mode, first actions, decision flow, recovery matrix, triage domains, maintenance entries, active issues, and safe next commands.
- `homenet doctor` exports `homenet.doctor.v1` as the live-evidence classifier. It classifies live findings into domains and links each issue to likely causes, first actions, source tools, runbook scenarios, and topology paths.
- `homenet scripts` exports `homenet.scripts.v1` as the script and runtime task inventory. It maps `maintenance/` scripts, systemd units, timers, and OpenWrt init entries to module owners and long-term dispositions without executing them.
- `homenet bundle` exports a read-only review directory with `homenet.bundle.v1` manifest, profiles, quickstart, module definitions, module artifact contracts, module renderer contracts, module implementation indexes, modules catalog, module registry, blueprint, ownership, status, runbook, topology, incident, doctor, secrets, inputs checklist, deployment worksheet, preflight, readiness, rollback, evidence, live proof, plan, metadata, artifacts, deploy dry-run, bootstrap plan, apply dry-run, write enablement, backup set, gates, change pack, pre-change proof contract, privacy audit, release boundary, public package, version, workspace, progress, render preview, config plan, rescue guide, scripts inventory, Kuma inventory, maintenance docs, verify report, and CI report. It writes only the requested output directory and does not read or mutate live infrastructure.
- `homenet docs` renders a Markdown maintenance guide from `homenet.metadata.v1`, including operations vocabulary, runtime targets, networks, Wi-Fi, devices, capability matrix, remote ingress, services, ports, checks, rollback, and privacy notes.
- `homenet kuma` exports `homenet.kuma_inventory.v1` as a read-only monitor candidate list grouped for Uptime Kuma.
- `homenet kuma --diff-db` exports `homenet.kuma_diff.v1` by reading an existing Uptime Kuma SQLite database in read-only immutable mode. It compares instance monitor candidates with live monitors and reports matched, changed, missing, extra, manual candidates, and interval drift without writing Kuma.
- `homenet kuma --diff-db --import-plan` exports `homenet.kuma_import_plan.v1`. It converts the diff into create, update, optional interval update, adopt-or-ignore, and manual actions. It remains read-only and treats extra Kuma monitors as operator-owned unless explicitly adopted.
- `homenet kuma --diff-db --import-plan --apply-db` exports `homenet.kuma_apply_result.v1`. It is dry-run by default; real writes require `--confirm-apply APPLY-KUMA`, create a timestamped Kuma DB backup before writing, create only missing automatic monitors by default, and never delete extra monitors.
- Service inventory supports multi-container ownership through `containers: [...]`. Docker live evidence uses the explicit container list when present and falls back to single-container `owner`, so multi-container services such as Shadowbroker are checked without special cases.
- HomeNet Ops now loads `homenet.metadata.v1` as its primary static data source, then derives frontend `instance` and `plan` views for the React app.
- Catalog-only background tasks can live in the selected instance `services.yaml`, keeping service inventory out of hardcoded UI logic.

Immediate next implementation work:

1. Keep real secrets in local secret storage only.
2. Implement write-side apply only after generated artifact review, backups, live verification, and token scoping are explicit.

## 16. Later Milestones

### Milestone 2: Config Generation

- Generate AdGuard upstream rules config.
- Generate Mihomo rule/provider skeletons.
- Generate OpenWrt review inventories.
- Generate Docker compose fragments for selected modules.

### Milestone 3: Safe Apply

- Implement backup and rollback.
- Apply OpenWrt-only non-disruptive changes first.
- Add explicit confirmation for network-disruptive operations.

### Milestone 4: OpenWrt-Only Runtime

- Provide lightweight DNS/proxy/status alternatives.
- Support routers with constrained storage and CPU.

### Milestone 5: Public Release

- Example instance.
- Quick Start.
- Maintenance guide.
- Security and secret-handling guide.
- Adoption guide from an existing home network.
