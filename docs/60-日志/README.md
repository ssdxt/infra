# 60 — 日志（Loki + Alloy 文件采集 + Grafana 看板 + logq）

> 资产：`/data1/ssdxt/logging/01-loki.sh`、`02-alloy.sh`、`03-grafana-loki-datasource.sh`、
> `04-make-loki-dashboard.py`、`logq.py`、`logging/README.md`（LogQL 速查手册）。
> 组件：Loki 3.3.2（chart 6.24.0，SingleBinary）+ Alloy 1.7.0（chart 0.12.0，DaemonSet 11/11）。

---

## 【原有功能】

- **Loki**（chart 原生）：日志存储与查询，SingleBinary + filesystem 存储。
- **Alloy**（chart 原生）：Grafana 家族的采集 agent，`loki.source.kubernetes` 组件支持从
  apiserver 流式拉容器日志（**本环境禁用**，原因见下）。

---

## 【后补调整】

### 1. Alloy 采集方式：apiserver 流式 → 读文件（关键架构决策）

- **改前现象**：初版用 `loki.source.kubernetes`（走 apiserver `pods/log`），11 节点 × 2632 个
  pods/log **CONNECT 长连接**（实测约 900 条并发流）直接压垮 apiserver——apiserver 请求
  指标异常，leader-election 受威胁。
- **改为文件采集**：读宿主机 `/var/log/pods/*/*/*.log`（containerd 落的 CRI 格式文件），
  **完全不经过 apiserver**。apiserver 压力归零。
- **配置要点**（全部在 `02-alloy.sh` 的 configMap 里，照抄即可）：
  ```river
  local.file_match "pods" {
    path_targets = [{ __path__ = "/var/log/pods/*/*/*.log", job = "pods" }]
  }
  loki.source.file "pods" {
    targets    = local.file_match.pods.targets
    forward_to = [loki.process.pods.receiver]
  }
  loki.process "pods" {
    stage.cri {}                       // 必须先剥 CRI 前缀 "<ts> stdout F <msg>"
    stage.regex {
      source     = "filename"          // 关键：从文件路径解析，不是日志行内容
      expression = "/var/log/pods/(?P<namespace>[^_]+)_(?P<pod>[^_]+)_(?P<pod_uid>[^/]+)/(?P<container>[^/]+)/.*"
    }
    stage.labels {
      values = { namespace = "", pod = "", container = "" }
    }
    stage.static_labels {
      values = { node = sys.env("NODE_NAME") }   // DaemonSet 注入的环境变量
    }
    forward_to = [loki.write.default.receiver]
  }
  loki.write "default" {
    endpoint { url = "http://loki.logging.svc.cluster.local:3100/loki/api/v1/push" }
  }
  ```
  chart values 要点：`alloy.mounts.varlog=true`（hostPath /var/log → /var/log 只读）、
  `extraEnv` 注入 `NODE_NAME=fieldRef spec.nodeName`、`controller.type=daemonset` +
  `tolerations: Exists`、`configReloader.enabled=false`（sidecar 镜像没进 Harbor，Alloy 自带热加载）。

### 2. Loki 部署参数（01-loki.sh）

```yaml
deploymentMode: SingleBinary
loki:
  auth_enabled: false
  commonConfig: {replication_factor: 1}
  storage: {type: filesystem}
  limits_config:
    retention_period: 168h          # 保留 7 天
    ingestion_rate_mb: 16
    ingestion_burst_size_mb: 32
  schemaConfig: {configs: [{from: "2024-01-01", store: tsdb, object_store: filesystem, schema: v13, index: {prefix: loki_index_, period: 24h}}]}
singleBinary:
  replicas: 1
  persistence: {enabled: true, size: 50Gi, storageClass: longhorn}   # 50Gi、Longhorn 2 副本、无备份
  resources: {requests: {cpu: 200m, memory: 512Mi}, limits: {memory: 2Gi}}
# 关掉重组件：backend/read/write/gateway/chunksCache/resultsCache/lokiCanary/test/minio 全 0/false
```
镜像由 `fix-chart-images.py` 改写为 Harbor（`logging/loki:3.3.2`、`logging/alloy:v1.7.0`、
`logging/k8s-sidecar:1.28.0`）。

**存储现状（务必知晓）**：PVC `storage-loki-0` 50Gi on longhorn（2 副本，数据在节点
`/data1/longhorn/`），**未配置 Longhorn backup target → 磁盘坏 = 日志丢**。想改保留期/容量/
副本数的方法见 `/data1/ssdxt/logging/README.md` §四的表。

### 3. Grafana 数据源与看板（ConfigMap 自动发现机制）

- **数据源**：`03-grafana-loki-datasource.sh` 建 ConfigMap `loki-datasource`（内容
  `apiVersion: 1; datasources: [{name: Loki, type: loki, url: http://loki.logging.svc.cluster.local:3100}]`）
  并打 **label `grafana_datasource=1`** → kube-prometheus-stack Grafana 的 sidecar
  （k8s-sidecar）自动加载该 ConfigMap 为数据源，脚本最后 rollout restart grafana。
- **看板同理**：带 **label `grafana_dashboard=1`** 的 ConfigMap 会被 sidecar 自动导入为看板。
  `04-make-loki-dashboard.py` 即按此机制生成 Loki 日志看板。
  ```bash
  bash /data1/ssdxt/logging/03-grafana-loki-datasource.sh
  python3 /data1/ssdxt/logging/04-make-loki-dashboard.py
  ```

### 4. logq.py 用法（不开 Grafana 查日志）

```bash
python3 /data1/ssdxt/logging/logq.py '{namespace="kube-system"} |= "error"'        # 查询（默认 20 条/1h）
python3 /data1/ssdxt/logging/logq.py '{namespace="longhorn-system", stream="stderr"}' 20 2h
python3 /data1/ssdxt/logging/logq.py -s 'sum by (pod) (count_over_time({namespace="kube-system"} |= "error" [5m]))' 1h
python3 /data1/ssdxt/logging/logq.py -l     # 列标签
python3 /data1/ssdxt/logging/logq.py -n     # 各命名空间日志量
```
原理：`kubectl exec loki-0 -c loki -- wget -qO- http://localhost:3100/loki/api/v1/...`，无需暴露端口。

---

## 【验证】

```bash
kubectl -n logging get pods                      # loki-0 1/1；alloy DaemonSet 11/11
kubectl -n logging exec loki-0 -c loki -- wget -qO- http://localhost:3100/loki/api/v1/labels
# 期望标签含 namespace/pod/container/node/stream/filename/job
python3 /data1/ssdxt/logging/logq.py '{job="pods"}' 5 10m
# Grafana Explore（https://<节点IP>:32298，admin/<GRAFANA_PASSWORD>）→ Loki → {namespace="kube-system"}，时间范围拉到 24h
```

---

## 日志告警（Loki Ruler → plant01 Alertmanager，2026-09-30 落地）

ruler 启用（`loki.rulerConfig`）、规则 ConfigMap（label `loki_rule: "1"` 同步 `/rules/fake`）、
两条正式规则（WxqLogErrorBurst / WxqOOMKilledDetected，warning→钉钉）+ 常驻链路测试规则
（WxqRulerLinkTest，none→不转发）、验证输出、加规则模板、回滚 —— **见 [loki-ruler.md](loki-ruler.md)**。

## 【回滚】

```bash
helm uninstall alloy -n logging      # 先停采集
helm uninstall loki -n logging       # 再删存储端（PVC 随 release 删除，日志即丢，慎用）
kubectl -n monitoring delete configmap loki-datasource
```
Alloy 单独回滚：`helm rollback alloy -n logging`（或改回流式 configMap 后 restart ds——**不要**，
会重新压垮 apiserver）。
