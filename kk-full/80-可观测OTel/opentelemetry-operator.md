# OpenTelemetry Operator（可观测性 · OTel）

> 落地时间：2026-09-29。状态：**已安装并通过冒烟验证**。
> 资产：`/data1/ssdxt/otel/`（values + 幂等安装脚本 + 冒烟样例），镜像在 Harbor `otel/` 项目。

## 【原有功能】

### 版本选择

| 组件 | 版本 | 说明 |
|---|---|---|
| opentelemetry-operator chart | **0.123.1** | open-telemetry 官方 helm repo 当时最新稳定 |
| operator（app version） | **0.159.0** | chart 默认自带，无需另选 |
| collector 镜像 | **0.159.0** | 与 operator 0.159.0 同版本发布，兼容性最有保障 |
| cert-manager（前置） | 1.16.1 | 已在集群，operator webhook 证书由其签发 |

版本来源：WSL 走代理 `helm search repo open-telemetry/opentelemetry-operator --versions`，取最新稳定 chart，其 app version 即 operator 版本；collector 用同版本 tag（0.159.0），避免兼容矩阵踩坑。

### 镜像清单（全部已进 Harbor `otel/` 项目，amd64）

| 源镜像（ghcr.io） | Harbor 目标 |
|---|---|
| `ghcr.io/open-telemetry/opentelemetry-operator/opentelemetry-operator:0.159.0` | `harbor.wuxing.local/otel/opentelemetry-operator:0.159.0` |
| `ghcr.io/open-telemetry/opentelemetry-collector-releases/opentelemetry-collector-k8s:0.159.0` | `harbor.wuxing.local/otel/opentelemetry-collector-k8s:0.159.0` |
| `ghcr.io/open-telemetry/opentelemetry-collector-releases/opentelemetry-collector:0.159.0` | `harbor.wuxing.local/otel/opentelemetry-collector:0.159.0` |

说明：
- `-k8s` 变体是 chart 默认给 `OpenTelemetryCollector` 实例用的镜像（含 k8s 相关 processor），**必须搬**；
- 纯 `opentelemetry-collector` 一起搬上，后续做独立网关 collector 时用；
- **用到时再搬**的：target-allocator（`opentelemetry-operator/target-allocator:0.159.0`，用 `mode: daemonset`+prometheus 抓取时）、opamp-bridge（远程配置）、各语言 auto-instrumentation 镜像（java/python/nodejs/python 等，做应用自动埋点时）。
- 搬运方式：WSL `skopeo copy --override-arch amd64 --dest-tls-verify=false --dest-creds admin:*** docker://ghcr.io/... docker://harbor.wuxing.local/otel/...`；清单已补进 `/data1/ssdxt/images/mirror.sh`（`bash mirror.sh otel`，备份 `mirror.sh.bak.20260929-otel`）。

### 安装命令

```bash
# chart 已上传 /data1/ssdxt/charts/opentelemetry-operator-0.123.1.tgz
bash /data1/ssdxt/otel/01-install-otel-operator.sh
# 等价手工命令：
helm install opentelemetry-operator /data1/ssdxt/charts/opentelemetry-operator-0.123.1.tgz \
  -n opentelemetry-operator-system --create-namespace \
  -f /data1/ssdxt/otel/otel-values.yaml
```

values 要点（`/data1/ssdxt/otel/otel-values.yaml`）：
- `manager.image` / `manager.collectorImage` 指向 Harbor；
- admissionWebhooks 保持默认 `certManager.enabled: true`（cert-manager 已在）；
- **必须关闭两个 networkpolicy feature gate**，见【后补调整】第 1 条。

### CRD 列表（安装后自动创建）

```
instrumentations.opentelemetry.io                v1alpha1
opampbridges.opentelemetry.io                    v1alpha1
opentelemetrycollectors.opentelemetry.io         v1alpha1,v1beta1
targetallocators.opentelemetry.io                v1alpha1
```

注意：新版本 CRD 组是 **`opentelemetry.io`**（旧文档/示例里的 `core.opentelemetry.io` 已废弃，写 yaml 时别照抄旧格式）。

### 冒烟验证（已验证 ✓）

样例：`/data1/ssdxt/otel/otel-smoke-collector.yaml`（deployment 模式，OTLP 收 → batch → debug 打印）。

```yaml
apiVersion: opentelemetry.io/v1beta1
kind: OpenTelemetryCollector
metadata:
  name: smoke
  namespace: opentelemetry-operator-system
spec:
  mode: deployment
  config:            # 注意：v1beta1 的 config 是【YAML 对象】，不是字符串！
    receivers:
      otlp:
        protocols:
          grpc: {}
          http: {}
    processors:
      batch: {}
    exporters:
      debug:
        verbosity: basic
    service:
      pipelines:
        traces:
          receivers: [otlp]
          processors: [batch]
          exporters: [debug]
```

验证步骤与实际输出：
1. Pod Running，镜像为 Harbor 的 `opentelemetry-collector-k8s:0.159.0`：
   `opentelemetrycollector.opentelemetry.io/smoke deployment 0.159.0 1/1 harbor.wuxing.local/otel/opentelemetry-collector-k8s:0.159.0 managed`
2. collector 启动日志：`Starting GRPC server ... endpoint: [::]:4317`、`Starting HTTP server ... [::]:4318`、`Everything is ready. Begin running and processing data.`
3. 发一条 OTLP/HTTP trace（protobuf 打到 svc:4318/v1/traces，HTTP 200），debug exporter 输出：
```
2026-09-29T16:49:19.038Z info Traces {"otelcol.component.id": "debug", "resource spans": 1, "spans": 1}
Span #0
    Trace ID       : cbc4288eef726825f246b83e1e883cf7
    Name           : smoke-trace-final
```
4. 验证完收尾：`kubectl delete otelcol smoke -n opentelemetry-operator-system`（已执行，不留实例）。

## 【后补调整】

### 1. 必须关闭 operator 的两个 networkpolicy feature gate（否则 operator 必挂）

- **改前现象**：operator 正常启动几十秒后到 kube-apiserver 的连接全部 `dial tcp 10.233.0.1:443: i/o timeout`，informer sync 超时 CrashLoop；apply otelcol 时 webhook 调用报 `failed calling webhook "mopentelemetrycollectorbeta.kb.io" ... operation not permitted`。
- **原因**：operator v0.159 默认开启 `operator.networkpolicy` / `operand.networkpolicy` 两个 feature gate，会给**自己和 operand 各建一个 NetworkPolicy**。其中 operator 自己那份 egress 只放行 EndpointSlice 发现的 apiserver **真实 IP:6443**（10.100.10.10/.14/.19），不放行 ClusterIP `10.233.0.1:443` → operator 被自己掐死；ingress 只放行 9443/8443 → apiserver 走 ClusterIP:443 调 webhook 也被拒。
- **精确改法**（`otel-values.yaml`）：
  ```yaml
  manager:
    featureGatesMap:
      operand.networkpolicy: false
      operator.networkpolicy: false
  ```
- **验证**：`kubectl get netpol -n opentelemetry-operator-system` 应为空；operator Pod 连续运行不重启、成功持有 lease；apply/delete otelcol 正常。
- **回滚**：把两个 gate 改回 true 并 `helm upgrade`（集群里需要 Cilium NetworkPolicy 正常工作的前提，本集群不需要）。
- **注意**：gate 只阻止新建，**不删已存在的 netpol**，脚本里已加 `kubectl delete netpol ... --ignore-not-found` 清理残留。

### 2. v1beta1 的 `spec.config` 是对象，不是字符串

- **改前现象**：按老文档写 `config: |`（多行字符串）apply 直接被 webhook 拒：`cannot unmarshal string into Go struct field ... spec.config of type v1beta1.Config`。
- **改法**：config 直接写 YAML 对象（见上方冒烟样例）。
- **回滚**：无（写法规范，非配置变更）。

### 3. CRD 组名迁移

- 老文档常见 `apiVersion: core.opentelemetry.io/v1beta1`；本版本是 `opentelemetry.io/v1beta1`。抄外部示例时注意替换。

## 常见坑 / 排障指南

| 症状 | 可能原因 | 排查命令 | 解法 |
|---|---|---|---|
| operator CrashLoop，日志 `dial tcp 10.233.0.1:443: i/o timeout` | 残留/自建 NetworkPolicy（见后补调整 1） | `kubectl get netpol -n opentelemetry-operator-system` | 关 gate + 删 netpol |
| apply otelcol 报 `failed calling webhook ... operation not permitted` | 同上（netpol 挡了 apiserver→webhook） | 同上 | 同上 |
| apply otelcol 报 `cannot unmarshal string ... spec.config` | config 写成了字符串 | — | config 写成 YAML 对象 |
| 报 `no matches for kind "OpenTelemetryCollecto" ...`（或 kind 缺字母） | CRD 组名/拼写错，或文件被 scp 截断 | `kubectl get crd \| grep otel`；文件内容用 `grep -c` 校验 | 用 `opentelemetry.io/v1beta1`；**Windows→服务器传文件一律 base64 中转**（本环境 scp 偶发丢字符，已两次踩坑） |
| 镜像 404 | ghcr 镜像没进 Harbor / tag 不对 | `skopeo inspect --tls-verify=false docker://harbor.wuxing.local/otel/<img>` | 走 WSL 代理重新 skopeo copy |
| webhook 起不来、证书报错 | cert-manager 不在或未就绪 | `kubectl get deploy -n cert-manager` | 先装 cert-manager（前置） |
| chart 版本 ↔ collector 镜像兼容 | collector 版本与 operator 不匹配可能拒绝启动（operator 会校验 operand 版本） | 看 operator 日志 | collector 用与 operator 相同的 0.159.0；升级时一起升 |

## 后续路线（未定，待排期）

1. 建**长期 collector 实例**：deployment 模式收集应用 trace（OTLP 入口），先导出到 **debug/Jaeger**——出口后端未定（候选：现 kube-prometheus-stack 之外新增 Jaeger，或 Tempo；待定）。
2. 应用接入两条路线（待定）：a) 应用直接 OTLP export 到 collector；b) operator `Instrumentation` CR + 自动埋点（需再搬 java/python 等 auto-instrumentation 镜像）。
3. 指标/日志链路是否并入 collector（现有 Prometheus remote_write、Loki+Alloy 已覆盖，避免重复采集）。

## 文件清单

| 位置 | 文件 | 用途 |
|---|---|---|
| control-01 `/data1/ssdxt/otel/` | `otel-values.yaml` | helm values（Harbor 镜像 + 关 netpol gate） |
| | `01-install-otel-operator.sh` | 幂等安装/升级脚本（含 netpol 残留清理） |
| | `otel-smoke-collector.yaml` | 冒烟样例（v1beta1 对象式 config） |
| control-01 `/data1/ssdxt/charts/` | `opentelemetry-operator-0.123.1.tgz` | 离线 chart |
| control-01 `/data1/ssdxt/images/` | `mirror.sh`（含 `LIST_OTEL`） | 镜像补货清单 |
