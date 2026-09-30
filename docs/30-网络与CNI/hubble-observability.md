# 30-网络与CNI §7 — Gateway/Hubble 可观测性（Hubble Relay+UI + 指标接入 Prometheus）

> 完成日期：2026-09-30。资产：control-01 `/data1/ssdxt/gateway/`（`03-hubble-observability.sh` 幂等脚本、
> `cilium-observability.yaml`、`cilium-gateway-dashboard.json`）。
> 镜像（Harbor 已备）：`cilium/hubble-relay:v1.20.1`、`cilium/hubble-ui:v0.13.5`、`cilium/hubble-ui-backend:v0.13.5`。

## 是什么

- **Hubble**：Cilium 的流量观测层（基于 eBPF），记录每个 L3-L7 流（五元组、verdict、DNS、HTTP）。
- **Hubble Relay**：汇聚 11 个节点 agent 的 Hubble 流（gRPC `:4244`），提供集群级流查询 API。
- **Hubble UI**：Web 界面，按命名空间/标签画服务依赖图、看实时流。本环境入口：
  **`https://hubble.wuxing.local:32298`**（工位 hosts 加 `10.100.10.10 hubble.wuxing.local`）。

## 改动（跑 `bash /data1/ssdxt/gateway/03-hubble-observability.sh`，幂等）

1. **helm 开关**（在 30 §1 流程上追加；⚠️ 每次升级后必须重做 4 项镜像修复，脚本已内置）：

```bash
helm upgrade cilium /data1/ssdxt/charts/cilium-1.20.1.tgz -n kube-system \
  -f /data1/ssdxt/cilium-values-before-hubble.yaml --reuse-values \
  --set hubble.relay.enabled=true --set hubble.ui.enabled=true \
  --set prometheus.enabled=true --set prometheus.port=9962 \
  --set hubble.relay.image.useDigest=false \
  --set hubble.ui.frontend.image.useDigest=false \
  --set hubble.ui.backend.image.useDigest=false
```

   `useDigest=false` 是军规（Harbor 单架构 digest 与上游不同，禁止 `@sha256:` 引用）。

2. **坑①：hubble-peer 的 `internalTrafficPolicy: Local`**（chart 模板写死，无 values 键）。
   KPR + hostPort 后端下 relay 连 ClusterIP 直接 connection refused → `NOT_SERVING` CrashLoop。
   修法：`kubectl -n kube-system patch svc hubble-peer --type merge -p '{"spec":{"internalTrafficPolicy":"Cluster"}}'`
   （⚠️ 每次 helm upgrade 后要重打，脚本已内置；日志看到 `Connected ... peer=wxq-*` ×11 即成功）。

3. **坑②：hubble UI 域名路由不要用 ExternalName 别名**（grafana 那套 ExternalName 模式对 Cilium
   Gateway 后端解析不稳定，实测 503 no healthy upstream）。正确姿势：HTTPRoute 直引
   `hubble-ui.kube-system:80` + kube-system ns 放 ReferenceGrant（见 `cilium-observability.yaml`）。

4. **指标接入**：3 个 headless Service（envoy 9964 / agent 9962 / operator 9963）+ 3 个
   ServiceMonitor（ns kube-system，**必须带 `release: prometheus-stack` 标签**才被 kps 收编）。
   agent 9962 默认不开，需 `--set prometheus.enabled=true --set prometheus.port=9962`。

5. **Grafana 面板**：`Cilium Gateway (wuxing.local)`（uid `cilium-gateway`），经 sidecar
   ConfigMap 通道导入（ns monitoring，label `grafana_dashboard: "1"`）。Grafana admin API 的
   basic-auth 密码与 secret 不一致（被 UI 改过），API 导入 401，故走 sidecar——**改面板就改
   ConfigMap，勿直接在 UI 保存**。

## 验证输出（2026-09-30 实测）

```
https hubble.wuxing.local:32298 -> 200
agent 9962: 200    envoy 9964: 200
Prometheus targets: {('cilium-agent-metrics','up'):11, ('cilium-envoy-metrics','up'):11, ('cilium-operator-metrics','up'):2}
relay 日志: Connected ... peer=wxq-* （11/11 节点）
grafana/longhorn/argocd 域名回归: 302/200/200；32298/32299 固定未漂移
```

## 面板与查询速查

- Grafana → Dashboards → `Cilium Gateway (wuxing.local)`：活跃连接、RPS、5xx、按后端（grafana/argocd/
  hubble-ui…）请求速率、Cilium 转发/丢弃、cilium 组件 up。
- 临时查流（有 hubble CLI 的机器）：`hubble observe --since 10m --port 32298`；
  无 CLI 可 `kubectl -n kube-system logs ds/cilium-envoy` 看访问日志。
- 排查路由：`kubectl -n gateway get httproute -o jsonpath=...conditions`（Accepted/ResolvedRefs）。

## 回滚

```bash
helm upgrade cilium /data1/ssdxt/charts/cilium-1.20.1.tgz -n kube-system \
  -f /data1/ssdxt/cilium-values-before-hubble.yaml --reuse-values \
  --set hubble.relay.enabled=false --set hubble.ui.enabled=false --set prometheus.enabled=false
# 然后重跑 30 §1 的 4 项镜像修复；删除：
kubectl delete -f /data1/ssdxt/gateway/cilium-observability.yaml
kubectl -n monitoring delete cm cilium-gateway-dashboard
```
