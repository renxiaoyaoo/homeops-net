# HomeNet

HomeNet 是一套可复用的家庭网络运维方案。它用 OpenWrt 做 Gateway，按需搭配 Pi、mini PC、NAS 或其他常在线主机，把 DNS split、Proxy、Remote Access、Monitoring、Service Directory 和排障入口放到一个清晰的操作模型里。

这个仓库的目标不是复制某一个家庭网络，而是把“一个可维护、可排障、可接管的家庭网络”抽象成公开 core。真实家庭网络只是它的部署实例。

## 最重要的原则

- **轻量优先**：默认只读、少脚本、少自动写入；复杂能力必须可选。
- **排障优先**：网络坏了时，先能判断坏在哪，再谈自动化。
- **术语诚实**：保留 Gateway、DNS、Proxy、TProxy、SSID、DHCP、WireGuard、Cloudflare Access 等真实术语，并解释它在家里负责什么。
- **Pi 可选**：有 Pi/mini PC/NAS 会更舒服，有历史和更多服务；没有也应该能跑 OpenWrt-only profile。
- **Source tool 不被取代**：OpenWrt、Mihomo、AdGuard、Kuma、Cloudflare、Home Assistant 仍是各自事实源；HomeNet 负责汇总、解释、生成审阅材料。

## 当前状态

当前重点是两件事：

1. 把 OpenWrt + 可选 server runtime 的家庭网络方案做成可部署、可使用、可接管的开源项目。
2. 让 HomeNet Ops 和 `homenet status` 作为辅助观测/排障入口，而不是部署主线。

HomeNet Ops 和 `homenet status` 都是 diagnostic-first：打开先看 Gateway/WAN、Wi-Fi radio、卧室 WRT、DNS/Proxy、Server Runtime、Remote Access、Smart Home / Apple Home、Rescue Path 和单设备身份，再进入服务清单、拓扑和工具入口。`status --live` 会把只读探针结果归到这些故障域，方便先定位层级再处理。

功能面按主线、辅助和高级审计分层维护，见 [docs/function-boundary.md](/home/pi/network/docs/function-boundary.md)。日常不要从完整命令索引开始。

## 新部署最短路径

新部署一个家时，不要先读完整命令索引。`./homenet --help` 只显示主路径；
完整命令索引用 `./homenet --help-all`。先运行交互式初始化：

```sh
./homenet init
```

它会询问实例名、部署形态、域名占位、OpenWrt IP、是否有 Pi/server、是否启用
Room AP、Maintenance Wi-Fi、Remote Access、Smart Home，然后生成私有 instance。
同一组回答重复运行是幂等的：目标目录内容一致时显示 unchanged；内容不同则默认
不覆盖，除非明确确认或使用 `--force`。

非交互或 CI 场景可以用：

```sh
./homenet init --yes --name my-home --profile openwrt-pi
```

初始化后走这条短路径：

```sh
./homenet deploy --instance instances/my-home --force --check-idempotent
./homenet status --instance instances/my-home --live
```

`quickstart` 的默认输出先给 First Deployment、Daily Use、Incident Response
和边界规则；module detail、dry-run apply、bundle、publish 等命令是第二层，
等第一轮实例能通过 CI 后再看。

没有常在线主机时：

```sh
./homenet init --profile openwrt-only
```

更高性能主机时：

```sh
./homenet init --profile openwrt-mini-pc
```

首次部署前只需要理解四个词：

- **Instance**：一个家的声明文件，主要是 `site.yaml`、`devices.yaml`、`services.yaml`。
- **Profile**：能力放在哪里跑，例如 `openwrt-only`、`openwrt-pi`、`openwrt-mini-pc`。
- **Module**：一个能力边界，例如 Gateway、DNS、Proxy、Remote Access、Observability、Maintenance Wi-Fi。
- **Source tool**：真正拥有设置的系统，例如 OpenWrt、Mihomo、AdGuard、Kuma、Cloudflare。

## 日常维护入口

当前家庭网络的日常入口：

- HomeNet Ops：家庭网络入口；先定位故障域，再给服务、拓扑、端口和 source tool 链接。
- HomeNet Ops 分流：临时把某个域名或 IP 切到 DIRECT、PROXY、PROXY-JAPAN、AI-NODES 或 IPV6-NODES；需要长期保留时先加入永久待提交。
- Uptime Kuma：告警和历史可用性。
- OpenWrt LuCI/UCI：Gateway、DHCP、Firewall、Wi-Fi。
- Mihomo Dashboard：Proxy 规则、节点、连接。
- AdGuard：DNS 行为和查询。
- Home Assistant：智能家居。
- Cloudflare Dashboard：Access、Tunnel、DNS。

CLI 的日常只读入口：

```sh
./homenet status --instance instances/my-home
./homenet incident --instance instances/my-home
./homenet topology --instance instances/my-home
./homenet doctor --instance instances/my-home
./homenet runbook --instance instances/my-home
./homenet rescue --instance instances/my-home
```

临时分流在 Ops 页面完成；永久待提交由 CLI 落到长期规则源：

```sh
./homenet routing status
./homenet routing commit
./homenet routing commit --confirm-permanent
```

网络已经出问题时，先用 HomeNet Ops；CLI 的顺序是：

```sh
./homenet incident --instance instances/my-home --live
./homenet status --instance instances/my-home --live
./homenet doctor --instance instances/my-home --live
./homenet check --instance instances/my-home --live
```

不要一上来重置路由器、重写配置或批量重启服务。先定位是哪一层：Gateway/WAN、Wi-Fi、Room AP、DNS/Proxy、Pi runtime、Remote Access、Smart Home / Apple Home，还是客户端自身。

首次安装或接管已有网络时，先用
`./homenet deploy --instance instances/my-home --force --check-idempotent`
生成最小部署包、查看 source-tool setup sequence，并证明重复生成不会漂移。

## 接管一个已有家庭网络

已有 OpenWrt、Pi、NAS、mini PC、AdGuard、Mihomo、Kuma、Cloudflare 或 Home Assistant 时，不要先重装。先把现状变成一个 instance，再按 source tool 小步接管：

```sh
./homenet init --name my-home --profile openwrt-pi
./homenet inputs --instance instances/my-home
./homenet deploy --instance instances/my-home --force --check-idempotent
./homenet check --instance instances/my-home
```

接管顺序是：

1. 先只整理 `site.yaml`、`devices.yaml`、`services.yaml`，不动现场网络。
2. 用 `deploy` 看 Gateway、DNS/Proxy、server runtime、Remote Access 的 source-tool 顺序并生成部署包。
3. 对每个 source tool 单独操作：OpenWrt 改 OpenWrt，Docker/systemd 改 server，Cloudflare 改 Cloudflare，Kuma 改 Kuma。
4. 每一步后跑 `check --live`、`status --live` 或 `doctor --live`，确认问题层级，不批量重启和重置。
5. HomeNet Ops/状态页面只用于观测和排障，不作为配置事实源。

更完整的部署和接管说明见 [docs/deployment-and-adoption.md](/home/pi/network/docs/deployment-and-adoption.md)。
最小部署形态见 [docs/minimal-deployment.md](/home/pi/network/docs/minimal-deployment.md)。
每个 source tool 的具体操作顺序见 [docs/source-tool-runbook.md](/home/pi/network/docs/source-tool-runbook.md)。

## 检修通道

实例应保留一个 Maintenance SSID 作为低依赖检修 Wi-Fi。它的定位是：

- 绕开透明代理和家庭 DNS。
- 允许设备直出公网。
- 保留到 Pi 的 SSH 和 HomeNet 访问。
- 当主网络、DNS 或 Proxy 异常时，让维护设备自己开代理访问 Codex，再让 Codex 进入 Pi 排查。

除非最基础的宽带、主路由或供电都坏了，否则这个通道应该能帮助远程维护。

## 目录边界

这个 workspace 是混合目录，不是一个可以整体开源的仓库。

可复用 public core：

- `homenet`
- `tools/homenet.py`
- `schemas/`
- `modules/`
- `templates/`
- `docs/`
- `instances/example-openwrt-pi/`
- `instances/example-openwrt-only/`
- 可复用的 `maintenance/` 辅助脚本和 systemd 示例

当前私有部署实例：

- private real-home instance, such as `instances/<private-home>/`
- 当前真实运行配置、运行数据、数据库、证书、订阅、token、key、备份

真实家庭部署应该就是这样的 private instance：它和公开 examples 使用同一套
HomeNet core、schema、module、deploy/check 和 live status 模型；区别只在于
真实设备、真实域名、运行目录和 secrets 不进入 public package。

工作区内的公开 app 和独立私有项目：

- `apps/ops/`：HomeNet Ops 应用源码，属于 HomeNet root。
- `sub/`：私有 Worker/订阅相关项目，有自己的边界。

确认边界：

```sh
./homenet workspace --instance instances/my-home
./homenet release --instance instances/my-home
./homenet version --instance instances/my-home
```

`workspace` 还会给出 Private Instance Boundary：如果以后要把真实家庭实例从混合
workspace 分离到私有目录或私有仓库，只复制 `site.yaml`、`devices.yaml`、
`services.yaml`、`README.md`，运行数据和 source tool 目录不跟着搬，接管前后用
`check`、`quickstart`、`workspace`、`deploy --check-idempotent` 验证。

## 开源包导出

准备 public package：

```sh
./homenet privacy --scope public
./homenet package --instance instances/my-home --output-dir /tmp/homenet-public
./homenet package-check --dir /tmp/homenet-public
./homenet package-smoke --dir /tmp/homenet-public
```

当前 `/home/pi/network` 也可以直接作为公开 repo clone 开发和推送 public core；
前提是先跑 privacy/check，并且 private instance、runtime、secrets 和 nested
private project 都保持 ignored/untracked。

导出的包会包含 `PUBLIC_PACKAGE.md`，它是给包接收者看的第一入口。发布者才需要继续使用
`release-candidate`、`publish-check`、`repo-init`、`publish-audit`、`repo-publish`。

## 维护前检查

改 root 仓库前：

```sh
./homenet privacy --scope public
./homenet check --instance instances/my-home
./homenet deploy --instance instances/my-home --force --check-idempotent
```

改 HomeNet Ops 前：

```sh
git status --short apps/ops
cd apps/ops/frontend
npm run check
npm run build
```

如果涉及 live network，先确认 source tool ownership，再小步操作。

## 延伸文档

- [docs/operator-path.md](/home/pi/network/docs/operator-path.md)：维护者最短路径。
- [docs/function-boundary.md](/home/pi/network/docs/function-boundary.md)：哪些功能是主线、辅助、高级审计或暂不做。
- [docs/minimal-deployment.md](/home/pi/network/docs/minimal-deployment.md)：最小部署形态和不做什么。
- [docs/deployment-and-adoption.md](/home/pi/network/docs/deployment-and-adoption.md)：部署、使用和接管主路径。
- [docs/source-tool-runbook.md](/home/pi/network/docs/source-tool-runbook.md)：OpenWrt、DNS、Proxy、server runtime、Cloudflare/Kuma 等 source tool 操作手册。
- [docs/homenet-design.md](/home/pi/network/docs/homenet-design.md)：产品和开源方案设计。
- [PUBLIC_PACKAGE.md](/home/pi/network/PUBLIC_PACKAGE.md)：导出包说明。
- [VERSIONING.md](/home/pi/network/VERSIONING.md)：版本化和 workspace 边界。
- [CONTRIBUTING.md](/home/pi/network/CONTRIBUTING.md)：贡献和 public/private 边界。
- [SECURITY.md](/home/pi/network/SECURITY.md)：安全报告和敏感信息处理边界。
- [PUBLISHING.md](/home/pi/network/PUBLISHING.md)：公开发布候选包、候选仓库和最终 push 步骤。
- [LICENSE](/home/pi/network/LICENSE)：MIT License。
