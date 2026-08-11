# HomeNet Ops

HomeNet Ops 是当前家庭网络的轻量 operations surface。它不替代 Uptime Kuma、AdGuard、Mihomo Dashboard 或 Home Assistant，只负责把“现在是否正常、坏在哪、从哪里进去、下一步做什么”放到一个页面里。

- Overview：当前结论、异常域、常用入口和下一步。
- Topology：家庭网络主路径、外部回家路径、检修通道和断电恢复检查。
- Services：按职责分组的服务目录、LAN/remote link 和端口用途。
- Routing：临时分流和永久规则候选。

职责分工：

- OpenWrt 仍是 Gateway、DHCP、防火墙、policy routing 的源头。
- AdGuard 仍是 DNS、广告拦截、查询日志的源头。
- Mihomo 仍是 rule matching、proxy groups、outbound chains 的源头。
- Home Assistant 负责家庭自动化和设备控制。
- Uptime Kuma 负责通知告警和可用性历史。
- Cloudflare Access/Tunnel 负责受保护的外部入口。
- HomeNet Ops 负责日常入口、当前状态、排障路径和配置来源提示；它只读观察，不代替源系统改配置。

## 技术栈

- 后端：`aiohttp`，继续复用现有 OpenWrt / Mihomo / AdGuard 采集逻辑，常驻模式下默认 15 秒采样一次。
- 前端：`React + TypeScript + Vite`，源码在 `frontend/`，构建产物在 `static/`。
- 视觉核心：React 页面内的 Overview、Topology、Services 和 Routing。
- 运行方式：一个 `homenet-ops` 容器直接监听 `9999`，不再额外维护 gate。
- 静态 metadata：通过只读挂载的 `/homenet-tools/homenet.py metadata` 生成 `homenet.metadata.v1`。部署时把私有 instance 目录挂载到 `/homenet-instance`。
- Blueprint：Ops 从同一份 metadata 派生 `homenet.blueprint.v1` 摘要，展示 HomeNet 的 product contract、active/fallback capabilities、operational questions 和 Source of Truth。
- 模块计划：从 `homenet.metadata.v1` 的 `module_plan` 派生，用于 Topology 的 Module Plan 和 Fix 的 module-level Checks / Rollback。

Primary operations entry：declared by the deployment instance remote entries, for example `https://ops.example.invalid/`.

LAN entries：`http://home.lan/` 或 `http://ops.lan/`

Fallback direct entry：`http://<server-lan-ip>:9999`

HomeNet Ops 容器直接监听 `9999`，由 Docker `restart: unless-stopped` 保持常驻。

## 依赖

运行在树莓派 Docker 上。它通过 SSH 只读访问 OpenWrt：

- 读取 `/sys/class/net/pppoe-wan/statistics/*`
- 读取 `/tmp/dhcp.leases`
- 读取 `ip neigh` 和 `/proc/net/nf_conntrack`，按连接字节差值计算每台设备的实时网速

域名实时网速来自树莓派 Mihomo：

- `http://127.0.0.1:9090/connections`
- `http://127.0.0.1:9090/traffic`
- 自动只读读取 `/home/pi/network/mihomo/config.yaml` 里的 controller secret，不需要手动填写

Health Checks 会在打开 HomeNet 主页面时刷新一次，只读不改配置：

- 读取 `/home/pi/network/adguard/conf/upstream-domestic.conf`
- SSH 到 OpenWrt 检查 `aweme.snssdk.com` 是否返回真实国内 IP
- SSH 到 OpenWrt 检查 `github.com` 是否返回 Mihomo fake-ip
- 用国内解析结果测试是否命中 OpenWrt `MIHOMO_CN4`
- SSH 到 OpenWrt 检查 maintenance SSID、DHCP、public DNS、Pi SSH/HomeNet allow rule、WAN allow rule、router management isolation、TProxy bypass

HomeNet 只做只读检查，不自动生成系统配置快照。

## 使用

```bash
homenet-ops url
```

然后打开脚本输出的地址，或使用 `http://<server-lan-ip>:9999`。

首次使用或代码依赖变化后构建镜像：

```bash
homenet-ops build
```

手动启动容器：

```bash
homenet-ops start
```

`start` 只启动本地已有镜像，不会拉 Docker Hub 或重新构建。

手动停止容器：

```bash
homenet-ops stop
```

其他命令：

```bash
homenet-ops status
homenet-ops logs
homenet-ops url
```

前台查看模式：

```bash
homenet-ops view
```

`view` 模式下按 `Ctrl-C` 会停止容器。

如果页面提示 OpenWrt SSH 失败，先在树莓派上做一次 SSH 免密：

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N "" 2>/dev/null || true
ssh-copy-id root@<openwrt-lan-ip>
ssh root@<openwrt-lan-ip> 'echo ok'
```

然后重启：

```bash
homenet-ops restart
```

## 确认没有后台运行

```bash
docker ps --filter name=homenet-ops
```

正常情况下应该看到正在运行的 `homenet-ops`。

## 强制停止

```bash
homenet-ops stop
```

## 命令安装

用户级命令位置：

```text
/home/pi/.local/bin/homenet-ops
```

从本目录脚本安装：

```bash
install -m 755 /home/pi/network/apps/ops/homenet-ops.sh /home/pi/.local/bin/homenet-ops
```

运行方式：

- 容器使用 host 网络，直接监听 `9999`。
- Caddy、Cloudflare Tunnel、`home.lan` / `ops.lan` 都指向这个入口。
- Services、端口总览、Access 入口、Blueprint 和 capability matrix 来自 `homenet.metadata.v1`；HTTP/TCP/UDP probes 由 metadata 的 service directory、port inventory 和少量 probe overrides 生成。
- 后台任务、维护 SSH 入口和没有 Web UI 的容器也应写在 instance metadata 中，不再靠 Ops 内部 catalog 硬编码。
- Topology 的 Module Plan 来自 `homenet.metadata.v1` 的 `module_plan`，显示每个 module 的 Placement、Checks 和 Rollback 摘要。
- Fix 的 Fault Paths 保留 Gateway / DNS / Proxy / Tunnel / Room AP / Maintenance Wi-Fi 等技术术语，用中文说明这些 module 在当前家庭网络里的职责。

## 说明

- 设备网速按 OpenWrt conntrack 字节计数计算，按 DHCP / 邻居表里的 MAC/IP/名称显示。
- 域名实时网速来自 Mihomo 活跃连接；没有经过 Mihomo 的连接可能只显示在设备流量里，不会显示域名。
- 设备最近 DNS 来自 OpenWrt dnsmasq query log，显示查询发生在多久前；这是 DNS 查询视角，不等同于实时连接流量。
- HTTPS/ECH/无 SNI 或没有被 Mihomo 识别的连接，可能显示为 IP。
- OpenWrt 需要开启 `net.netfilter.nf_conntrack_acct=1`。当前家里路由器已开启；如果以后刷机后页面没有设备网速，再检查这一项。
- OpenWrt 需要开启 `dhcp.@dnsmasq[0].logqueries=1`。当前已开启，用于“设备最近 DNS”。
