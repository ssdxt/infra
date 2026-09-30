# wxq 集群交付目录说明（/data1/ssdxt）

> 所有可复现的安装材料、脚本、文档都在这里。每个子目录都有一份 README.md 说明"怎么装、怎么改、怎么验"。

---

## 🔔 待办 / 到期提醒（请定期检查）

| 到期/待办 | 时间 | 说明 | 详情 |
|---|---|---|---|
| **⚠️ Longhorn webhook leaf 证书到期** | **2027-08 之前必须手工轮转**（证书 2027-09-29 到期） | 该证书已被设为 `listener.cattle.io/static=true`，**不再自动续期**。过期会导致 Longhorn admission webhook 全量失败（failurePolicy=Fail），无法创建/修改任何 Longhorn CR | `storage/longhorn-webhook-tls-issue.md` §0 |
| Longhorn webhook CA 证书到期 | 2036-09-26 | 有效期 10 年，远期 | 同上 |
| 升级 Longhorn 以彻底消除 webhook Secret 抖动 | 建议排期 | 当前 1.7.2 命中上游 #13012；官方在 v1.12.0 修复并 backport 到 v1.11.3。升级后可用官方机制替代 `static` 注解，同时恢复自动续期 | `storage/longhorn-webhook-tls-issue.md` §3 方案 B |
| **etcd 监控缺口未修** | 建议尽快 | Prometheus 里 etcd **0 series**（etcd 是 systemd 服务而非静态 Pod，ServiceMonitor 端点发现为 0）。目前无法观测 etcd fsync 延迟/db 大小/leader 抖动 | `storage/longhorn-webhook-tls-issue.md` §7 |
| Longhorn CSI / cilium-operator 仍有少量重启 | 观察中 | 已消除应用层压力（apiserver 请求 -97%、429 归零），残余抖动疑似来自 etcd 磁盘延迟；待 etcd 监控打通后定位 | `etcd-disk-requirement.md` |

---

## 目录导航

| 目录 | 内容 | 关键脚本 |
|---|---|---|
| `charts/` | 所有 helm 图表包（cilium / cert-manager / kube-prometheus-stack / gateway-api / nodelocaldns / **longhorn-1.7.2 / loki-6.24.0 / alloy-0.12.0**） | — |
| `values/` | 已部署组件的 values 快照（回滚/复刻用） | — |
| `tools/` | 通用工具 | `fix-chart-images.py`（自动把图表镜像改写为 Harbor） |
| `images/` | 镜像搬运 | `mirror.sh`（skopeo 批量搬 amd64 镜像到 Harbor，18 个镜像） |
| `storage/` | 共享存储（NFS + Longhorn） | `01-nfs-server-plant02.sh`、`02-nfs-client-nodes.sh`、`03-longhorn-install.sh` |
| `storage/crds/` | external-snapshotter 的 VolumeSnapshot CRD（Longhorn csi-snapshotter 前置） | 直接 `kubectl apply -f` |
| `storage/backup/` | Secret 备份（含 Longhorn webhook 证书） | — |
| `monitoring/` | 监控增强 | `01-metrics-server.sh`、`02-remote-write.sh` |
| `logging/` | 日志体系（Loki + Alloy） | `01-loki.sh`、`02-alloy.sh`、`03-grafana-loki-datasource.sh` |
| `gateway/` | Gateway API 对外暴露（持久化） | `01-deploy.sh` |

## 当前集群已部署的组件（2026-09-29）

| 组件 | 命名空间 | 访问方式 |
|---|---|---|
| Cilium 1.20.1（KPR 模式） | kube-system | — |
| cert-manager 1.16.1 | cert-manager | — |
| kube-prometheus-stack 62.7.0 | monitoring | Grafana `admin/prom-operator` |
| **Longhorn 1.7.2**（2 副本、数据在 `/data1/longhorn`、`longhorn` 为 default SC） | longhorn-system | `kubectl -n longhorn-system port-forward svc/longhorn-frontend 8080:80` |
| **Loki 6.24.0**（SingleBinary，PVC 50Gi on longhorn） | logging | `http://loki.logging.svc.cluster.local:3100`（已接入 Grafana 数据源） |
| **Alloy 0.12.0**（DaemonSet，11/11，读宿主机 `/var/log/pods` 文件采集） | logging | — |
| **metrics-server v0.7.2** | kube-system | `kubectl top nodes/pods` |
| nodelocaldns | kube-system | — |
| Gateway API（GatewayClass: cilium） | — | 待建 Gateway |

## Harbor 账号
- 地址 `harbor.wuxing.local`（10.100.10.29）
- 账号 `admin` / `<HARBOR_PASSWORD>`
- CA 证书：`/etc/docker/certs.d/harbor.wuxing.local/ca.crt`（各节点已信任）
- 节点侧 containerd 已配置 `insecure_skip_verify = true` + 认证（见 `/etc/containerd/config.toml`）

## 重要约定（调整时请遵守）

1. **镜像全部走 Harbor**，绝不依赖外网（要新镜像用 `images/mirror.sh` 搬；清单已含 18 个镜像）
2. **chart 的镜像路径用 `tools/fix-chart-images.py` 自动改写**，不要手工猜 values 路径
   ```bash
   python3 tools/fix-chart-images.py <chart.tgz> <项目名> harbor.wuxing.local /tmp/out.yaml
   ```
   - 规则：若该镜像块同时含 `registry` 字段 → `registry=<域名>` + `repository=<项目>/<仓库末段>`；否则 → `repository=<域名>/<项目>/<仓库末段>`（**直接拼接 registry+repository 的 chart 必须按前一种写法，否则会出现 `harbor.wuxing.local/harbor.wuxing.local/...` 双重前缀**）
3. **helm upgrade cilium 后必须重跑镜像修正**（见 `集群改造详细命令记录.md` 第二章）
4. **暴露服务用 Gateway，不要用 nohup 端口转发**
5. **改动前先备份**：所有脚本改动都会留 `.bak.<时间戳>`，Secret 改动前导出完整 yaml 到 `storage/backup/`
