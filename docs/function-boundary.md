# HomeNet 功能边界

HomeNet 的主线不是做一个巨大的自动化平台，而是让一个家庭网络可以被部署、使用、排障和接管。命令很多时，按下面分层理解。

## 主线功能

这些是必须保留、优先维护的功能。

| 功能 | 命令/入口 | 用途 |
| --- | --- | --- |
| 初始化实例 | `homenet init` | 交互式生成一个家的 `site.yaml`、`devices.yaml`、`services.yaml`。 |
| 生成部署材料 | `homenet deploy --check-idempotent` | 生成最小部署包，并证明重复生成结果稳定。 |
| 静态校验 | `homenet check` | 校验实例、schema、设备、服务、入口声明。 |
| 当前状态 | `homenet status` / Ops | 看当前网络、服务、拓扑、入口和异常域。 |
| 排障 | `homenet incident` / `doctor` / `rescue` | 网络慢、断网、外部回家失败、设备异常时先定位层级。 |
| 服务/拓扑 | Ops Services / Topology | 给人看的入口、端口、服务位置、断电恢复视图。 |
| 临时分流 | Ops Routing / `homenet routing` | 临时或永久候选地调整单个域名/IP 的代理策略。 |

## 辅助功能

这些有用，但不应该出现在第一屏或新用户主路径里。

| 功能 | 命令/入口 | 用途 |
| --- | --- | --- |
| Source tool 边界 | `ownership` / `workspace` / `version` | 明确什么归 OpenWrt、Mihomo、AdGuard、Kuma、Cloudflare、Ops 管。 |
| 维护文档 | `docs` / `runbook` / `topology` | 生成或查看维护说明。 |
| Kuma 候选 | `kuma` | 给告警系统提供 monitor 候选和差异检查。 |
| Cloudflare 核对 | `status --live` / Cloudflare provider check | 只读核对 Access、Tunnel、远程入口和本地服务目标。 |
| 隐私/发布边界 | `privacy` / `release` / `package-check` | 防止把私有实例、密钥、运行数据放进公开包。 |

## 高级审计功能

这些只给维护者、发布者、未来自动化使用。它们不属于日常使用路径。

| 功能 | 命令 |
| --- | --- |
| 发布候选 | `package`、`package-smoke`、`release-candidate`、`publish-check`、`repo-init`、`repo-publish` |
| Review bundle | `bundle`、`render`、`generate` |
| 未来写入审计 | `apply --dry-run`、`gates`、`evidence`、`live-proof`、`write-enablement` |
| 未来执行/备份合同 | `exec-plan`、`backup-plan`、`backup-set`、`change-pack`、`pre-change-proof`、`change-record-check` |
| 模块内部索引 | `module-*`、`artifacts`、`module-registry` |

高级审计功能当前的价值是保留安全边界和未来扩展合同；它们不应该推动 HomeNet 变成大型平台。如果维护成本继续升高，应优先删除或合并这些命令，而不是继续拆文件。

## 暂不做

- 不让 HomeNet 自动写 OpenWrt 配置。
- 不让 HomeNet 自动重构真实网络拓扑。
- 不在当前阶段实现 WDS/802.11s 迁移。
- 不升级 OpenWrt 作为 HomeNet 功能的一部分。
- 不继续增加大量探针；新探针必须证明能减少排障时间。
- 不把 Ops 做成复杂 dashboard；Ops 只回答“现在怎样、坏在哪、从哪里进、下一步做什么”。

## 精简原则

1. 主线命令坏了优先修。
2. 辅助命令如果和主线重复表达，删辅助表达。
3. 高级审计命令如果长期没人用，只保留文档和 schema 思路，不保留完整 CLI 面。
4. `tools/homenet.py` 不再为了拆而拆；优先把主线稳定下来，再决定是否重写高级审计层。
5. Ops 不再加功能，只减信息密度和修错误。
