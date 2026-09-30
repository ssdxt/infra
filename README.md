# infra — 离线 K8s 集群完整复刻仓库

> **目标：任何人拿到这个仓库，就能从零把这套离线 K8s 集群完整复刻出来。**
> 复刻手册入口：[`docs/99-全新环境复刻手册.md`](docs/99-全新环境复刻手册.md)，引导脚本：[`bootstrap/bootstrap.sh`](bootstrap/bootstrap.sh)

---

## 30 秒总览

一套 **KubeKey 部署的离线 K8s 1.37 集群**（control-01/02/03 + plant01/02 等 worker，节点网段 10.100.10.0/24），
Cilium 全家桶做网络/可观测，Longhorn 做分布式存储，Harbor（harbor.wuxing.local，10.100.10.29）做内网镜像源，
Prometheus 全家桶 + Loki + OTel 做监控日志，Tetragon/Kyverno 做安全，ArgoCD 做 GitOps。

| 层 | 组件 | 版本 | 事实来源 |
|---|---|---|---|
| 网络 CNI | Cilium（加密/带宽/BGP/KPR/Hubble） | 1.20.1 | `values/cilium-values-unified.yaml` |
| 网关 | Gateway API + Cilium Gateway | experimental CRD | `charts/gateway-api/` |
| DNS | NodeLocal DNSCache | — | `charts/nodelocaldns.yaml` |
| 存储 | Longhorn（1.7.2 → 1.13.0 升级链全保留） | 1.13.0 | `charts/longhorn/` + `values/longhorn-values-harbor-*.yaml` |
| 监控 | kube-prometheus-stack | 62.7.0 | `values/prometheus-stack-values.yaml`（含 remoteWrite 固化） |
| 自定义指标 | prometheus-adapter（cpu2/mem2Gi） | 5.3.0 | `values/prometheus-adapter-values.yaml` |
| 弹性伸缩 | KEDA | 2.21.0 | `values/keda-values.yaml` |
| etcd 监控 | etcd SSL 指标打通 | — | `scripts/40-monitoring/04-etcd-monitoring.sh` |
| 日志 | Loki + Alloy + Ruler（告警规则） | 6.24.0 / 0.12.0 | `values/loki-ruler*.yaml` |
| 证书 | cert-manager | 1.16.1 | `values/cert-manager-values.yaml` |
| 安全 | Tetragon（基线策略+Grafana 看板） | 1.7.1 | `values/tetragon-values.yaml` |
| 策略 | Kyverno（注入代理策略） | 3.9.1 | `values/kyverno/` |
| GitOps | ArgoCD | 3.5.3 | `scripts/70-gitops/`（待接内网 git） |
| OTel | opentelemetry-operator | 0.123.1 | `scripts/40-monitoring/otel-*` |
| 镜像 | Harbor 离线镜像仓 | — | `images/mirror.sh`（skopeo 全量清单） |

---

## 架构图（ASCII）

```
                    ┌──────────────────────── 工位/运维机（外网侧，WSL+skopeo） ────────────────┐
                    │  images/mirror.sh ──skopeo copy──>  Harbor (harbor.wuxing.local 10.100.10.29)
                    └──────────────────────────────────┬───────────────────────────────────┘
                                                       │ 内网 10.100.10.0/24（离线）
  ┌────────────────────────────────────────────────────┼──────────────────────────────────────────┐
  │  control-01 (10.100.10.10)   control-02   control-03          plant01 / plant02 / ... worker │
  │  ┌─────────────────────────── K8s 1.37 (KubeKey) ───────────────────────────┐               │
  │  │  Cilium 1.20.1 ( WireGuard加密 | BGP | KPR | Hubble | 带宽 CNI带宽管理 ) │               │
  │  │  Gateway API (Cilium Gateway, TLS: wxq-root-ca)     NodeLocalDNS        │               │
  │  ├──────────────────────── 存储 ────────────────────────────────────────────┤               │
  │  │  Longhorn 1.13.0 (UI basic-auth 反代, snapshot-controller, webhook TLS) │               │
  │  ├──────────────────────── 监控/日志 ───────────────────────────────────────┤               │
  │  │  kube-prometheus-stack 62.7.0 ──remoteWrite──> 远端 VictoriaMetrics     │               │
  │  │     │ etcd-SSL 指标 │ prometheus-adapter(cpu2/mem2Gi) │ KEDA 2.21       │               │
  │  │  Loki 6.24 + Alloy(DaemonSet 采集) + Ruler(钉钉告警) │ OTel Operator    │               │
  │  ├──────────────────────── 安全 ────────────────────────────────────────────┤               │
  │  │  Tetragon 1.7.1 (基线策略+看板) │ Kyverno 3.9.1 (egress 注入代理策略)   │               │
  │  ├──────────────────────── GitOps ──────────────────────────────────────────┤               │
  │  │  ArgoCD 3.5.3 (Gateway HTTPS: argocd.wuxing.local:32298)                │               │
  │  └──────────────────────────────────────────────────────────────────────────┘               │
  │  系统层: chrony 修复 │ etcd 快盘迁移 │ kubelet 镜像GC/预留 │ containerd 迁移 data1 │ apt 加固 │
  └─────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 完整复刻顺序（按编号执行，每步给出脚本/文档）

**0. 前置准备**
- 节点规划、IP、密码方案、Harbor 地址：[`docs/00-环境清单.md`](docs/00-环境清单.md)
- 消毒说明：本仓库所有明文密码已替换为占位符（`<ROOT_PASSWORD>` / `<HARBOR_PASSWORD>` /
  `<ARGOCD_INITIAL_PASSWORD>` / `<LONGHORN_UI_PASSWORD>` / `<GRAFANA_PASSWORD>` / `<DINGTALK_TOKEN>`），
  使用前先在本地还原为真实密码。
- SSH 免密/配置：`scripts/00-bootstrap/control01-ssh-config.md`

**1. 镜像准备（先把全家桶搬进 Harbor）**
- [`images/mirror.sh`](images/mirror.sh)：skopeo 全量清单（`LIST_*` 分类，71+18+…全部镜像，amd64 单架构），
  在能出外网的机器（WSL）执行，Harbor 走 NO_PROXY 直连。
- Kyverno 独立清单：`scripts/50-security/kyverno-mirror.sh`；OTel：`scripts/40-monitoring/otel-*`。

**2. KubeKey 装集群**
- kk 配置样例与安装步骤：[`docs/10-k8s-install/README.md`](docs/10-k8s-install/README.md)
- 装完先打节点标签：`scripts/00-bootstrap/node-labels.sh`；引导目录/基础配置：`scripts/00-bootstrap/bootstrap-dirs.sh`

**3. 系统层加固（全部在 `scripts/10-system/`）**
- chrony/NTP 修复：`fix-chrony-ntp.sh`（或 `fix-chrony2.sh`，诊断用 `diag-chrony.sh`）
- etcd 快盘迁移（数据盘换 SSD）：`etcd-migrate-to-fastdisk.sh` + `etcd-prepare.sh` / `etcd-cutover.sh` /
  `etcd-final-verify.sh` / `etcd-steady-check.sh`，实录见 [`docs/40-存储/etcd换盘迁移实录.md`](docs/40-存储/etcd换盘迁移实录.md)
- kubelet 镜像 GC 调优：`kubelet-imagegc-tune.sh` + `finish-imagegc.sh`
- containerd 数据目录迁移到 data1：`containerd-relocate.sh`（方案：[`docs/20-系统层调整/08-containerd迁移data1方案.md`](docs/20-系统层调整/08-containerd迁移data1方案.md)）
- kubelet 资源预留：`kubelet-reserve.sh`；apt/自动更新管控与加固：`apt-hardening.sh`
- 心跳 watchdog：`install-heartbeat.sh`

**4. Cilium 全家桶**
- **唯一事实来源**：[`values/cilium-values-unified.yaml`](values/cilium-values-unified.yaml)
  （WireGuard 加密、带宽管理、egress 网关、BGP、KPR、Hubble、全量 Harbor 镜像地址）
- 安装：`helm upgrade --install cilium charts/cilium-1.20.1.tgz -n kube-system -f values/cilium-values-unified.yaml`
- 升级三铁律与回归清单：[`docs/30-网络与CNI/cilium-full-stack.md`](docs/30-网络与CNI/cilium-full-stack.md)（同一份在 `values/cilium-full-stack.md`）
- Gateway API：先装 CRD `charts/gateway-api/experimental-install.yaml`，再执行
  `scripts/30-network/01-gateway-deploy.sh` → `02-gateway-https.sh`（HTTPRoute+TLS，根证书 `wxq-root-ca.crt`）
- NodeLocalDNS：`charts/nodelocaldns.yaml` + `scripts/30-network/nodelocaldns-fix.sh`
- Hubble：`scripts/30-network/03-hubble-observability.sh`，文档 [`docs/30-网络与CNI/hubble-observability.md`](docs/30-网络与CNI/hubble-observability.md)

**5. 存储（Longhorn → 1.13 升级链）**
- 前置 NFS（备份）：`scripts/20-storage/01-nfs-server-plant02.sh`、`02-nfs-client-nodes.sh`
- 安装 1.7.2：`scripts/20-storage/03-longhorn-install.sh`（chart `charts/longhorn-1.7.2.tgz`）
- 升级链 **1.7.2 → 1.8.2 → 1.9.2 → 1.10.2 → 1.11.3 → 1.12.1 → 1.13.0**：
  chart 全在 `charts/longhorn/`，每版对应 values `values/longhorn-values-harbor-*.yaml`，
  全程实录与坑：[`docs/40-存储/longhorn-upgrade-1.7.2-to-1.13.0.md`](docs/40-存储/longhorn-upgrade-1.7.2-to-1.13.0.md) +
  `scripts/20-storage/longhorn-webhook-tls-issue.md`（webhook TLS 坑）
- snapshot-controller + CRD：`scripts/20-storage/crds/` + `snapshot-controller.yaml`
- 清理 localpv：`04-remove-localpv.sh`；UI basic-auth 反代：`longhorn-ui-auth-proxy.sh`

**6. 监控（`scripts/40-monitoring/`）**
- metrics-server：`01-metrics-server.sh`
- kube-prometheus-stack 62.7.0：`install-kube-prometheus-stack.sh`（chart `charts/kube-prometheus-stack-62.7.0.tgz`，
  values [`values/prometheus-stack-values.yaml`](values/prometheus-stack-values.yaml)：remoteWrite 固化 + grafana extraEnv + priorityClassName）
- remote-write 固化：`02-remote-write.sh` + `remote-write-desired.json`（问题记录 [`docs/50-监控/remote-write-问题记录.md`](docs/50-监控/remote-write-问题记录.md)）
- etcd 监控打通：`04-etcd-monitoring.sh` + `manifests/etcd-monitoring.yaml`（[`docs/50-监控/etcd-监控打通.md`](docs/50-监控/etcd-监控打通.md)）
- KEDA：`05-install-keda.sh`；prometheus-adapter：`03-prometheus-adapter.sh`（调优见 [`docs/50-监控/prometheus-adapter.md`](docs/50-监控/prometheus-adapter.md)）
- watchdog 反向心跳与静音：[`docs/50-监控/watchdog-反向心跳与静音.md`](docs/50-监控/watchdog-反向心跳与静音.md) + `scripts/99-ops/plant01-*`

**7. 日志（Loki + Alloy + Ruler）**
- 安装：`loki-install.sh` / `alloy-install.sh` / `grafana-loki-datasource.sh`
- Ruler 告警规则：[`values/loki-ruler.yaml`](values/loki-ruler.yaml) + [`values/loki-ruler-rules.yaml`](values/loki-ruler-rules.yaml)
  （文档 [`docs/60-日志/loki-ruler.md`](docs/60-日志/loki-ruler.md)）
- 看板：`make-loki-dashboard.py`；日志查询工具 `logq.py`

**8. 安全（`scripts/50-security/`）**
- Tetragon：`01-install-tetragon.sh` + 基线策略 `policies-baseline.yaml` + PDB `priority-pdb.yaml`（文档 [`docs/85-安全/Tetragon.md`](docs/85-安全/Tetragon.md)）
- Kyverno：`install-kyverno.sh` + 注入代理策略 [`values/kyverno/inject-proxy-policy.yaml`](values/kyverno/inject-proxy-policy.yaml)（[`docs/30-网络与CNI/kyverno-egress-injection.md`](docs/30-网络与CNI/kyverno-egress-injection.md)）
- Longhorn UI basic auth：`scripts/20-storage/longhorn-ui-auth-proxy.sh`（[`docs/40-存储/longhorn-ui-auth.md`](docs/40-存储/longhorn-ui-auth.md)）

**9. GitOps（ArgoCD，待内网 git）**
- `scripts/70-gitops/01-install-argocd.sh`（Harbor 化清单 `argocd-install-harbor.yaml`）
- HTTPS 暴露：`scripts/30-network/argocd-httproute.yaml`；文档 [`docs/70-GitOps/argocd.md`](docs/70-GitOps/argocd.md)

**10. 验收清单**
- 告警清零：`scripts/99-ops/alerts-today-summary.sh`、`analyze-alert-sources.py`
- 组件全绿：`scripts/99-ops/status-all.sh`、`monitor-check.sh`
- 磁盘治理：`scripts/99-ops/disk-diag.sh`、`plant01-disk-alert.sh`
- 总验收：`scripts/99-ops/acceptance.sh`

---

## 已知坑索引（必读）

全部集中在 [`docs/90-踩坑与修复记录/README.md`](docs/90-踩坑与修复记录/README.md)，重点：

- **PowerShell 剥双引号**：从 Windows 往 Linux 传命令/脚本时双引号会被剥掉 → 一律 tar 打包 + scp 拉回，
  解包后抽查关键脚本首尾行完整性（scp 大文件偶发丢字符）。
- **digest 404**：skopeo/Harbor 按 digest 拉取偶发 404 → 用 tag + `--dest-verify-https=false` 重试。
- **Cilium upgrade 三铁律**：见 `values/cilium-full-stack.md`（升级前备份 values、CRD 先行、逐条回归 hubble/kpr/加密）。
- Longhorn webhook TLS 升级连环坑：`scripts/20-storage/longhorn-webhook-tls-issue.md`
- etcd 换盘的 OOM/抖动坑：`docs/40-存储/etcd换盘迁移实录.md`
- Kyverno 注入策略导致 DNS 异常的定位：`scripts/30-network/test-kyverno-dns.py`

---

## 目录导航

```
infra/
├── README.md                 ← 本文件
├── docs/                     ← kk-full 文档总集（00 环境清单 … 99 复刻手册，保持章节结构）
├── charts/                   ← 全部 helm chart tgz + gateway-api CRD + nodelocaldns + longhorn 升级链
├── values/                   ← 所有组件 values（cilium-unified 为网络层唯一事实来源）
├── images/mirror.sh          ← skopeo 全量镜像清单
├── scripts/
│   ├── 00-bootstrap/         ← 新环境引导
│   ├── 10-system/            ← 系统层加固（chrony/etcd 快盘/GC/containerd/预留/apt）
│   ├── 20-storage/           ← Longhorn 安装+升级链+快照+UI auth
│   ├── 30-network/           ← Gateway/Hubble/Kyverno 注入策略
│   ├── 40-monitoring/        ← prom-stack/remote-write/etcd/keda/adapter/loki/otel
│   ├── 50-security/          ← tetragon/kyverno
│   ├── 70-gitops/            ← argocd
│   └── 99-ops/               ← 日常运维实战脚本（磁盘/告警/DNS/adapter 调优…）
└── bootstrap/bootstrap.sh    ← 端到端引导入口
```

---

## 变更纪律（军规）

1. **任何**对集群的调整（helm values、脚本、策略、系统层），必须在当天同步回本仓库对应目录。
2. 改 values 先改 `values/` 里的事实来源文件，再应用到集群；禁止只在集群上 `helm upgrade --set`。
3. 新踩的坑必须写入 `docs/90-踩坑与修复记录/`，并在本 README 坑索引中加一行。
4. 凭据永远不进仓库：用占位符；GitHub PAT 等外网凭据绝不出现。
5. 破坏性操作（etcd 迁移、Longhorn 升级、containerd 迁移）必须先备份（参考 `scripts/20-storage` 中 backup 步骤）再执行。
