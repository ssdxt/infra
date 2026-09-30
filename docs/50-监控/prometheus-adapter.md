# prometheus-adapter（HPA 自定义指标 API）

> 目标：为 HPA 提供 `custom.metrics.k8s.io/v1beta1` API，从 monitoring 里的 Prometheus 读指标。
> 资产三件套（control-01）：
> - 安装脚本：`/data1/ssdxt/monitoring/03-prometheus-adapter.sh`（幂等）
> - values：`/data1/ssdxt/values/prometheus-adapter-values.yaml`
> - Chart 包：`/data1/ssdxt/charts/prometheus-adapter-5.3.0.tgz`（离线安装用，不再访问外网 repo）
>
> 镜像清单已补进 `/data1/ssdxt/images/mirror.sh`（`monitoring` 目标）。

## 版本与镜像

| 项 | 值 |
|---|---|
| Chart | prometheus-community/prometheus-adapter **5.3.0** |
| Adapter | **v0.12.0**（= chart appVersion，values 里 `tag: v0.12.0` 显式写死） |
| 镜像 | `harbor.wuxing.local/monitoring/prometheus-adapter:v0.12.0`（唯一镜像，无 init/sidecar） |
| 上游源 | `registry.k8s.io/prometheus-adapter/prometheus-adapter:v0.12.0` |
| 副本 | 2（chart 的 key 是 `replicas:`，**不是** `replicaCount:`） |

WSL 搬运（新环境复刻用）：

```bash
# WSL 内；拉上游走代理，推 Harbor 直连
export HTTPS_PROXY=http://127.0.0.1:12450
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts --force-update
helm pull prometheus-community/prometheus-adapter --version 5.3.0
export NO_PROXY=harbor.wuxing.local,10.100.10.29,127.0.0.1
skopeo copy --override-arch amd64 \
  docker://registry.k8s.io/prometheus-adapter/prometheus-adapter:v0.12.0 \
  docker://harbor.wuxing.local/monitoring/prometheus-adapter:v0.12.0 \
  --dest-tls-verify=false --dest-creds admin:'<HARBOR密码>'
# tgz 上传：scp prometheus-adapter-5.3.0.tgz root@10.100.10.10:/data1/ssdxt/charts/
```

## 【原有功能】

chart 开箱能力，只讲怎么正确启用：

- `rules.default: true`：启用 adapter 内置 resource 规则，把 Prometheus 里的 cAdvisor/kube-state-metrics
  指标映射成 `pods/...`、`namespaces/...`、`nodes/...` 命名的自定义指标（含 `pods/cpu_usage`、
  `pods/memory_usage_bytes`、`nodes/...` 等利用率/用量类），HPA 按 CPU/内存扩缩即可工作。
- `prometheus.url/port`：adapter 的数据源。本集群指向 kube-prometheus-stack 的 Prometheus：
  `http://prometheus-stack-kube-prom-prometheus.monitoring:9090`。
- 证书：adapter 自签 serving cert 并通过 APIService 对接聚合层，**不需要 cert-manager**，
  chart 自带 `--cert-dir=/tmp/cert` 自签逻辑，无需额外配置。

安装（幂等，可重复跑；control-01 上执行）：

```bash
export KUBECONFIG=/etc/kubernetes/admin.conf
bash /data1/ssdxt/monitoring/03-prometheus-adapter.sh
```

脚本内容等价于：

```bash
helm upgrade --install prometheus-adapter /data1/ssdxt/charts/prometheus-adapter-5.3.0.tgz \
  -n monitoring -f /data1/ssdxt/values/prometheus-adapter-values.yaml
kubectl -n monitoring rollout status deploy/prometheus-adapter --timeout=300s
```

## 【后补调整】

### 1. 内存 512Mi 会被 OOMKill —— 提到 1Gi

- **改前现象**：Pod 起来后 20 秒左右被杀，`CrashLoopBackOff`，日志无 panic。
- **原因**：`kubectl describe pod` 显示 `Last State: Terminated / Reason: OOMKilled / Exit Code: 137`。
  默认规则启动时要对全集群指标做首次 relist + 规则评估，监控指标基数大（本集群 API 返回 6546 个资源名），
  512Mi limit 撑不过启动期。
- **改法**：`/data1/ssdxt/values/prometheus-adapter-values.yaml`：
  ```yaml
  resources:
    requests: { cpu: 100m, memory: 256Mi }
    limits:   { cpu: 500m, memory: 1Gi }
  ```
- **验证**：重跑安装脚本后 `kubectl -n monitoring get pods -l app.kubernetes.io/name=prometheus-adapter`
  两副本 1/1 Running，RESTARTS=0（实际输出见下文验证节）。
- **回滚**：`helm -n monitoring rollback prometheus-adapter <旧revision>`。

### 2. 副本数 key 是 `replicas` 不是 `replicaCount`

- **改前现象**：values 写 `replicaCount: 2` 后部署仍只有 1 个 Pod。
- **原因**：这个 chart 的 values key 是 `replicas:`（chart values.yaml 第 47 行）。
- **改法**：values 里用 `replicas: 2`。
- **验证**：`kubectl -n monitoring get deploy prometheus-adapter` 显示 `2/2`。
- **回滚**：无副作用，改回即生效。

### 3. values 禁用 digest 引用

镜像一律显式 `repository: harbor.wuxing.local/monitoring/prometheus-adapter` + `tag: v0.12.0`，
不写 `@sha256:`（单架构复刻会改摘要导致 404），与全仓规矩一致。

## 安装后验证（实际输出）

环境：`export KUBECONFIG=/etc/kubernetes/admin.conf`（control-01，2026-09-29 实测）。

① Pod Running（2 副本）：

```
$ kubectl -n monitoring get pods -l app.kubernetes.io/name=prometheus-adapter
NAME                                 READY   STATUS    RESTARTS   AGE
prometheus-adapter-849996849-f45bb   1/1     Running   0          5m17s
prometheus-adapter-849996849-g5hwh   1/1     Running   0          43s
```

② APIService AVAILABLE=True：

```
$ kubectl get apiservice v1beta1.custom.metrics.k8s.io
NAME                            SERVICE                         AVAILABLE   AGE
v1beta1.custom.metrics.k8s.io   monitoring/prometheus-adapter   True        13m
```

③ custom metrics API 返回资源列表（共 6546 个，含 pods/namespaces/nodes 资源指标）：

```
$ kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1 | head -c 200
{"kind":"APIResourceList","apiVersion":"v1","groupVersion":"custom.metrics.k8s.io/v1beta1",
 "resources":[{"name":"namespaces/alertmanager_silences_query_duration_seconds_sum",...
```

④ 资源指标可查到具体值（含 `pods/cpu_usage`、`pods/memory_usage_bytes`、
`namespaces/cpu_usage`、`nodes/...` 等）：

```
$ kubectl get --raw '/apis/custom.metrics.k8s.io/v1beta1/namespaces/monitoring/pods/prometheus-adapter-849996849-f45bb/cpu_usage'
{"kind":"MetricValueList","apiVersion":"custom.metrics.k8s.io/v1beta1","metadata":{},"items":[
 {"describedObject":{"kind":"Pod","namespace":"monitoring","name":"prometheus-adapter-849996849-f45bb","apiVersion":"/v1"},
  "metricName":"cpu_usage","timestamp":"2026-09-29T14:07:45Z","value":"563m","selector":null}]}
```

helm 记录：`prometheus-adapter  monitoring  deployed  prometheus-adapter-5.3.0  v0.12.0`。

## HPA 使用示例

### A. 按 CPU（metrics-server 的 resource 指标，走 metrics.k8s.io）

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: demo-app-cpu
  namespace: default
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: demo-app
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

### B. 按自定义指标（走 prometheus-adapter，`pods/cpu_usage`）

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: demo-app-custom
  namespace: default
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: demo-app
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Pods
      pods:
        metric:
          name: cpu_usage        # adapter 默认规则暴露的指标名
        target:
          type: AverageValue
          averageValue: "500m"   # 每 Pod 目标值
```

### 验证 HPA

```bash
export KUBECONFIG=/etc/kubernetes/admin.conf
kubectl get hpa -A
kubectl describe hpa demo-app-custom -n default   # 看_conditions 里的 SuccessfulRescale / AbleToScale
```

期望输出形如：

```
$ kubectl get hpa
NAME              REFERENCE              TARGETS   MINPODS   MAXPODS   REPLICAS   AGE
demo-app-custom   Deployment/demo-app    563m/500m   2         10        3          5m
```

> 排障：若 HPA `TARGETS` 显示 `<unknown>`，先确认
> `kubectl get --raw '/apis/custom.metrics.k8s.io/v1beta1/namespaces/<ns>/pods/*/cpu_usage'`
> 能返回值；APIService 若 AVAILABLE=False，看 `kubectl -n monitoring logs deploy/prometheus-adapter`
> 与 Prometheus URL 连通性。

## 相关文件

- 脚本：[C:\Users\CC\Desktop\dsh 相对仓库] 与 control-01 `/data1/ssdxt/monitoring/03-prometheus-adapter.sh`
- values：control-01 `/data1/ssdxt/values/prometheus-adapter-values.yaml`
- 镜像清单：control-01 `/data1/ssdxt/images/mirror.sh`（新增 `LIST_MONITORING`，`bash mirror.sh monitoring` 可重放）
- Chart：control-01 `/data1/ssdxt/charts/prometheus-adapter-5.3.0.tgz`
