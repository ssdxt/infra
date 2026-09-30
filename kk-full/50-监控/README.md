# 50 — 监控（kube-prometheus-stack / remote_write / metrics-server / etcd 盲区 / adapter）

> 资产：`/data1/ssdxt/charts/kube-prometheus-stack-62.7.0.tgz`、`values/prometheus-stack-values.yaml`、
> `monitoring/01-metrics-server.sh`、`monitoring/02-remote-write.sh`、`monitoring/03-prometheus-adapter.sh`、
> `monitoring/04-etcd-monitoring.sh` + `monitoring/manifests/04-etcd-monitoring.yaml`、`monitoring/README.md`。

---

## §1 kube-prometheus-stack 62.7.0 安装与全部 values 调整

**【原有功能】** chart 一键装 Prometheus + Alertmanager + Grafana + operator + node-exporter +
kube-state-metrics，自带 230 条告警规则与 27 个看板。

**【后补调整】（安装顺序即踩坑顺序，照抄即可）**

1. **首次安装先关 admission webhook**（chart 的 certgen 镜像 `kube-webhook-certgen` 没进 Harbor）：
   ```bash
   helm install prometheus-stack /data1/ssdxt/charts/kube-prometheus-stack-62.7.0.tgz \
     -n monitoring --create-namespace \
     --set prometheusOperator.admissionWebhooks.enabled=false \
     --timeout 15m
   ```
2. **镜像路径：必须三段式 `registry + repository + tag`**。只改 repository 会拼出
   `quay.io/harbor.wuxing.local/...`。另外 **Prometheus/Alertmanager 服务端镜像的键在
   `prometheus.prometheusSpec.image` / `alertmanager.alertmanagerSpec.image`**
   （改子 chart 的 `prometheus.image` 不生效）。最终 values 已存
   `/data1/ssdxt/values/prometheus-stack-values.yaml`，键路径对照表：
   | 组件 | 键路径 | Harbor 路径 |
   |---|---|---|
   | operator | `prometheusOperator.image` | monitoring/prometheus-operator:v0.76.1 |
   | config-reloader | `prometheusOperator.prometheusConfigReloader.image` | monitoring/prometheus-config-reloader:v0.76.1 |
   | Prometheus | `prometheus.prometheusSpec.image` | monitoring/prometheus:v2.54.1 |
   | Alertmanager | `alertmanager.alertmanagerSpec.image` | monitoring/alertmanager:v0.27.0 |
   | Grafana | `grafana.image` | monitoring/grafana:11.2.0 |
   | Grafana init | `grafana.initChownData.image` | library/busybox:1.38.0 |
   | Grafana sidecar | `grafana.sidecar.image` | monitoring/k8s-sidecar:1.27.4 |
   | node-exporter | `prometheus-node-exporter.image` | monitoring/node-exporter:v1.8.2 |
   | kube-state-metrics | `kube-state-metrics.image` | monitoring/kube-state-metrics:v2.13.0 |
   ```bash
   helm upgrade prometheus-stack /data1/ssdxt/charts/kube-prometheus-stack-62.7.0.tgz \
     -n monitoring --reuse-values -f /data1/ssdxt/values/prometheus-stack-values.yaml --timeout 15m
   ```
3. **node-exporter 端口改 9101**：节点 9100 已被占用（hostPort 冲突
   `bind: address already in use`）→ values 里 `prometheus-node-exporter.service.{port,targetPort}=9101`。
4. **operator 卡 ContainerCreating（tls-secret 死锁）**：关 webhook 后 chart 不再创建
   admission secret，operator 仍要挂 → values 里 `prometheusOperator.tls.enabled=false`，
   并清掉卡住的非 Running Pod。
5. **config-reloader 是独立镜像**（不在 operator 里，报
   `stat /bin/prometheus-config-reloader: no such file`）→ WSL 拉
   `quay.io/prometheus-operator/prometheus-config-reloader:v0.76.1` 推 Harbor（见 00-环境清单 §5 链路）。

验证：
```bash
kubectl get pods -n monitoring
# 期望：node-exporter 11 个、kube-state-metrics 1/1、operator 1/1、grafana 3/3、
#       prometheus-0 2/2、alertmanager-0 2/2
# Grafana：https://<节点IP>:32298（即 https://grafana.wuxing.local:32298，2026-09-30 起 HTTPS+泛域名证书）
# admin 密码已固化进 values（grafana.adminPassword）——网页端改密码会被 helm upgrade 覆盖回退，必须改 values：
#   /data1/ssdxt/values/prometheus-stack-values.yaml → grafana.adminPassword（2026-09-30 固化）
```

---

## §2 remote_write → plant01

**【后补调整】** 本集群 Prometheus 本地 retention 10d + emptyDir（重启丢历史）；
长期数据推 plant01（10.100.10.29:9091）。

- **前置**：plant01 Prometheus 需带 `--web.enable-remote-write-receiver` 启动（报 404 就是没开）；
  plant01 侧 `retention.size=25GB` 控制占用。
- **精确改法（2026-09-30 起已固化进 values，此前靠 kubectl patch + 每次升级重跑 02 脚本）**：
  `/data1/ssdxt/values/prometheus-stack-values.yaml` → `prometheus.prometheusSpec`：
  ```yaml
  externalLabels: {cluster: wxq}      # 补上了文档声称但曾丢失的集群标识
  remoteWrite:
  - url: http://10.100.10.29:9091/api/v1/write
    remoteTimeout: 60s
    queueConfig: {batchSendDeadline: 60s, maxBackoff: 30s, maxSamplesPerSend: 2000,
                  maxShards: 1, minBackoff: 500ms, minShards: 1, sampleAgeLimit: 1h}
    writeRelabelConfigs:
    - action: keep    # 只推核心 job，省带宽
      regex: (kubelet|node-exporter|kube-state-metrics|apiserver|etcd|kube-scheduler|kube-controller-manager|coredns|prometheus-stack-kube-prom-prometheus|prometheus-stack-kube-prom-alertmanager|prometheus-stack-kube-prom-operator)
      sourceLabels: [job]
    - action: drop    # histogram _bucket 序列量大，丢弃省带宽（100Mbps 网络）；
      regex: .*_bucket  # 代价：plant01 侧算不了 histogram p99，需回本集群查
    - {action: drop, regex: kubernetes_feature_enabled, sourceLabels: [__name__]}
    - {action: drop, regex: ALERTS, sourceLabels: [__name__]}
    - {action: drop, regex: ALERTS_FOR_STATE, sourceLabels: [__name__]}
    - {action: drop, regex: count:up0, sourceLabels: [__name__]}
    - {action: drop, regex: count:up1, sourceLabels: [__name__]}
  ```
  `02-remote-write.sh` + `remote-write-desired.json` 降级为**应急恢复工具**（values 意外丢失时手工 patch），不再必跑。
  固化时已验证：helm upgrade（rev 10）后 CR 的 remoteWrite 与 `remote-write-desired.json` **逐字段一致**。
- **验证**：
  ```bash
  kubectl -n monitoring logs prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus | grep -i remotewrite
  # plant01 Grafana 查询 up{cluster="wxq"} 看 job 列表
  ```
- **回滚**：values 删 remoteWrite/externalLabels 后 helm upgrade（应急可用 02 脚本把 CR 置空）。

---

## §3 metrics-server（0.7.2）

**【原有功能】** 无（prometheus-stack 不提供 metrics.k8s.io API）。

**【后补调整】** 清单式安装（非 helm），全部镜像只有一个：
`harbor.wuxing.local/metrics-server/metrics-server:v0.7.2`。

```bash
bash /data1/ssdxt/monitoring/01-metrics-server.sh
```

关键点：
- args 必含 `--kubelet-insecure-tls`（kubelet 自签证书）与
  `--kubelet-preferred-address-types=InternalIP`；
- **坑：缺 `system:auth-delegator` 绑定** → APIService `v1beta1.metrics.k8s.io` 一直
  `Unavailable`，`kubectl top` 报 error。清单里的
  `ClusterRoleBinding metrics-server:system:auth-delegator`（绑定到内置
  `system:auth-delegator`）就是修这个的，删不得；另有 kube-system 里的
  `metrics-server-auth-reader` RoleBinding（extension-apiserver-authentication-reader）。

验证：
```bash
kubectl get apiservice v1beta1.metrics.k8s.io    # 期望 AVAILABLE=True
kubectl top nodes && kubectl top pods -A | head
```

回滚：`kubectl delete -f <由脚本生成的清单>`（脚本直接 apply stdin，可先
`kubectl get deploy metrics-server -n kube-system -o yaml > backup.yaml` 留底）。

---

## §4 etcd 监控打通 ✅（systemd etcd → 静态 Endpoints + mTLS，2026-09-30 已解决）

> **完整实录见 [etcd-监控打通.md](etcd-监控打通.md)**。此处仅留结论。

**【后补调整·已完成】** etcd 是 systemd 服务（非静态 Pod），chart 自带 etcd Service/SM 匹配
0 Pod + 2379 强制 mTLS，双重失效 → 0 series。

- **根因**：Service selector `component=etcd` 匹配 Pod（systemd 形态永远 0 个）；SM 默认
  http 抓 2381（本集群无此端口）。
- **精确改法（方案①，不动 etcd）**：自建三件套（`/data1/ssdxt/monitoring/manifests/04-etcd-monitoring.yaml`）：
  无 selector Service `etcd-monitor`（port 名 `http-metrics`:2379）+ 静态 Endpoints
  三台 IP:2379 + ServiceMonitor（https + Secret `kube-etcd-client-certs` 三证书 +
  `insecureSkipVerify: true` + job 固定 `kube-etcd`）。证书 Secret 由
  `/etc/kubernetes/pki/etcd/` 生成（脚本 `04-etcd-monitoring.sh`，幂等）。
  Prometheus 挂证书已**固化进 values**（`prometheus.prometheusSpec.secrets`），
  helm upgrade 一次到位，升级后照军规 7 重跑 02/03。
- **验证**：`up{job="kube-etcd"}` 3 台全 1；fsync p99 **5.0~7.9ms**（旧盘 fio 24~27ms，
  印证换盘收益）；Grafana `Kubernetes / etcd` 看板核心面板全部出数（`cluster` 隐藏变量
  自动解析为 `kube-etcd`，看板零改动）。
- **回滚**：delete 三件套 + Secret；values 删 `secrets` 后 upgrade。

---

## §5 KubeProxyDown 误报消除（kubeProxy.enabled=false）

**【后补调整】**

- **改前现象**：告警 `KubeProxyDown` 常驻误报（kube-proxy DaemonSet 已被 KPR 删除，
  其 ServiceMonitor 无 target）。
- **精确改法**：values 里（已固化进 `/data1/ssdxt/values/prometheus-stack-values.yaml`）：
  ```yaml
  kubeProxy:
    enabled: false     # 关闭 kube-proxy 的 ServiceMonitor 与告警规则
  ```
  ```bash
  helm upgrade prometheus-stack /data1/ssdxt/charts/kube-prometheus-stack-62.7.0.tgz \
    -n monitoring --reuse-values -f /data1/ssdxt/values/prometheus-stack-values.yaml
  ```
- **验证**：`kubectl -n monitoring get servicemonitor | grep kube-proxy` → 无；Alertmanager
  不再收到 KubeProxyDown。
- **回滚**：去掉该 values 键重新 upgrade。

---

## §6 chrony 告警

**【后补调整】** 节点时钟漂移曾达 0.9~1.4s（20-系统层 §1），依赖两条现成指标/规则盯防：

```promql
node_timex_sync_status == 0                    # 节点 NTP 未同步（期望 11 台全 1）
|delta(node_timex_offset_seconds[10m])| > 0.1  # 时钟偏差变化过大
```

内置规则集无 chrony 专项告警时，用 PrometheusRule 补（namespace monitoring，label
`release: prometheus-stack` 让 sidecar 加载）：
```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: chrony-rules
  namespace: monitoring
  labels: {release: prometheus-stack}
spec:
  groups:
  - name: chrony
    rules:
    - alert: NodeTimeNotSynced
      expr: node_timex_sync_status == 0
      for: 10m
      labels: {severity: warning}
      annotations: {summary: "节点 {{ $labels.instance }} NTP 未同步"}
```
修复动作见 20-系统层 §1。验证：修复后 `node_timex_sync_status` 全 1，告警恢复。

---

## §7 prometheus-adapter（HPA 指标）

> ⏳ **占位：另一个智能体正在安装，本节由安装智能体补充。**
>
> 预留要点：镜像 `harbor.wuxing.local/<项目>/prometheus-adapter:<tag>` 需先经 WSL 搬运；
> 需要配 `prometheus.url`（集群内 `http://prometheus-stack-kube-prom-prometheus.monitoring:9090`）、
> rules 与 `custom.metrics.k8s.io`/`external.metrics.k8s.io` APIService；完成后回填安装命令、
> values、验证（`kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1`）与回滚。
