# kk-full — KubeKey 离线集群完整部署与调整手册

> 目标：拿着本目录 + /data1/ssdxt/ 的脚本资产，能在**任何一个新环境**从零复刻整套集群，并理解每一处"为什么"。
> 铁律：**从今天起，任何人对集群做的任何调整（哪怕改一行配置），都必须同步补充到本目录对应章节，否则视为没做。**

## 目录结构（按技术栈分类）

```
kk-full/
├── README.md                  本文件：规矩 + 导航
├── 00-环境清单.md              网段/主机/凭据/离线源/代理 —— 复刻前提
├── 10-k8s-install/            KubeKey 安装本体（原有功能 + 安装配置）
├── 20-系统层调整/              chrony、journald、etcd.env、内核、时钟等系统级
├── 30-网络与CNI/              Cilium(KPR)、kube-vip、Gateway API、nodelocaldns
├── 40-存储/                   Longhorn、NFS、VolumeSnapshot、磁盘验收/迁移
├── 50-监控/                   kube-prometheus-stack、metrics-server、remote_write、
│                              prometheus-adapter(HPA)、etcd监控盲区
├── 60-日志/                   Loki、Alloy、Grafana 数据源与看板、logq 工具
├── 70-GitOps/                 ArgoCD
├── 80-可观测OTel/             OpenTelemetry Operator
├── 85-安全/                   Tetragon（eBPF 运行时安全：观察基线策略 + Grafana 看板）
├── 90-踩坑与修复记录/          每个坑：现象/根因/修复/验证（含 Windows 侧工具坑）
└── 99-全新环境复刻手册.md      端到端顺序步骤（新环境照着敲）
```

> 每个子目录的 `README.md` 即该章正文；文档事实基线以 [00-环境清单.md](00-环境清单.md) 为准，
> 端到端操作顺序见 [99-全新环境复刻手册.md](99-全新环境复刻手册.md)。
> 新增组件详情：[50-监控/prometheus-adapter.md](50-监控/prometheus-adapter.md)、
> [70-GitOps/argocd.md](70-GitOps/argocd.md)、[80-可观测OTel/opentelemetry-operator.md](80-可观测OTel/opentelemetry-operator.md)、
> [85-安全/Tetragon.md](85-安全/Tetragon.md)、
> [50-监控/remote-write-问题记录.md](50-监控/remote-write-问题记录.md)、
> [30-网络与CNI/cilium-full-stack.md](30-网络与CNI/cilium-full-stack.md)（Cilium 统一 values + 四开关 + 回归清单）、
> [60-日志/loki-ruler.md](60-日志/loki-ruler.md)（Loki 日志告警 ruler→plant01 AM→钉钉）。

## 复刻军规（规矩）

1. **两类分开写**：每个章节必须分两块——
   - 【原有功能】：安装包/Chart 本身开箱提供的能力，只讲怎么正确启用
   - 【后补调整】：我们踩坑后改的东西。每条必须有：**改前现象 → 原因 → 精确改法（命令/文件/行）→ 验证方法 → 回滚方法**
2. **命令可直接复制执行**：所有命令写全（含 KUBECONFIG、命名空间、路径），变量用 `<大写占位>` 并解释
3. **离线优先**：任何镜像必须先进 Harbor（`harbor.wuxing.local`）；只取 **amd64**（`skopeo copy --override-arch amd64`）；**禁止在 values/清单里用 `@sha256:` 摘要引用**（单架构复刻会改变摘要导致 404），一律显式写 `仓库:tag`
4. **可重复执行**：脚本必须幂等（重跑不炸），改动前自动备份（`.bak.日期`）
5. **双份落地**：文档写进本目录（C 盘 kk-full），可执行脚本/清单同步到 control-01 `/data1/ssdxt/` 对应子目录
6. **证据说话**：验证步骤必须贴原始输出（kubectl/helm/curl 的实际返回）
7. **helm upgrade 后必须重跑监控补丁脚本**（remoteWrite 已固化进 values，02-remote-write.sh 降级为应急；upgrade 后只需 `bash /data1/ssdxt/monitoring/03-prometheus-adapter.sh`，etcd 三件套同已固化无需重跑）。
   **Cilium 专属附加（2026-09-30 起）**：任何 cilium helm upgrade 必须
   ① 用统一 values `-f /data1/ssdxt/values/cilium-values-unified.yaml`（唯一事实来源，禁 --set 零散打点）；
   ② **禁用 `--wait`**（operator 命令被 chart 渲染成 cilium-operator-generic 必 CrashLoop，详见 30 章 §8）；
   ③ 升级后重打 3 补丁（operator command / hubble-peer Cluster / gateway nodePort）并跑 30 章 §8 回归清单。
   监控原文：

## 当前组件清单（速览）

| 技术栈 | 组件 | 版本 | 状态 |
|---|---|---|---|
| K8s | KubeKey 安装 | v1.37.0 / kk v4.0.7-patched | 运行中 |
| CNI | Cilium（KPR，替代 kube-proxy） | 1.20.1 | 运行中（+Hubble Relay/UI，见 30 章 §7；全栈开关 WireGuard/带宽/Egress/BGP 已启用，见 30 章 §8） |
| VIP | kube-vip | — | 运行中（10.100.10.250） |
| Ingress | Cilium Gateway API | — | 10.100.10.251 |
| DNS | CoreDNS + nodelocaldns | — | 11/11 |
| 证书 | cert-manager | 1.16.1 | 运行中 |
| 监控 | kube-prometheus-stack | 62.7.0 | 运行中（remote_write→plant01） |
| 指标 | metrics-server | 0.7.2 | 运行中（kubectl top 可用） |
| HPA | prometheus-adapter | 0.12.0 (chart 5.3.0) | 运行中（custom.metrics API 可用；与 KEDA 共存，下线另议） |
| 伸缩 | KEDA（事件驱动伸缩） | 2.21.0 | 运行中（external.metrics API 可用，prometheus 触发全链路验证通过，见 50-监控/keda.md；demo 样例保留于 keda-demo ns） |
| 日志 | Loki + Alloy（文件采集） | 3.3.2 / 1.7 | 运行中（Grafana 看板已建） |
| 存储 | Longhorn（默认SC，2副本）+ NFS(plant02) | 1.13.0（2026-09-30 由 1.7.2 逐版本升级，见 40-存储/longhorn-upgrade-1.7.2-to-1.13.0.md） | 运行中（CSI 快照链路已修复） |
| GitOps | ArgoCD | 3.5.3 | 运行中（域名入口 https://argocd.wuxing.local:32298，NodePort 已清理）；GitHub 同步已配代理链路（10.100.10.14:8888），⚠️ 该代理上游 2026-09-30 起黑洞暂不可用，待修复后即通（见 70-GitOps/argocd.md §7） |
| OTel | OpenTelemetry Operator | 0.159.0 | 运行中（冒烟通过） |
| 安全 | Tetragon（eBPF 运行时安全） | 1.7.1 | 运行中（DS 11/11；观察基线策略 5 条 + Grafana 看板 + ServiceMonitor，见 85-安全/Tetragon.md） |
| 策略 | Kyverno（按 ns 标签注入出网代理 env） | 1.19.1 (chart 3.9.1) | 运行中（resource webhook failurePolicy=Ignore；kube-system 排除；见 30-网络与CNI/kyverno-egress-injection.md） |

## 未决事项（换 etcd 高性能盘后收尾）

- etcd 专用盘 50G×3 到位后：`/data1/ssdxt/storage/05-etcd-migrate-to-fastdisk.sh`（check→prepare→cutover 逐台）
- 换盘稳定 24h 后：恢复租约参数（etcd 10s→2.5s 等，脚本 `restore-timers` 子命令）
- etcd 监控打通 ✅（方案①已落地，见 50-监控/etcd-监控打通.md；fsync p99 实测 5~8ms）
- plant01 的 docker-compose.yaml 已重建；~~Longhorn webhook 证书 2027-08 前必须手工轮转~~ ✅ 已作废（2026-09-30 升级 Longhorn 1.13.0 后移除 static 注解，官方修复生效，dynamiclistener 自动管理恢复，见 40-存储/README.md §2）
- PSS 安全基线（Pod Security Standards restricted 级）待启用：Kyverno 已就位（2026-09-30），直接引用官方 pod-security 策略集按命名空间标签灰度即可，扩展方向见 [30-网络与CNI/kyverno-egress-injection.md](30-网络与CNI/kyverno-egress-injection.md) §6
