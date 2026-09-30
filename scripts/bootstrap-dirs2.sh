#!/bin/bash
# 补建 logging / gateway 目录 + 归位工具与镜像脚本
set -e
R=/data1/ssdxt
H=harbor.wuxing.local

# ---- 归位工具 ----
mkdir -p $R/tools $R/images $R/gateway
cp -f /tmp/fix-chart-images.py $R/tools/ 2>/dev/null || true
chmod +x $R/tools/*.py 2>/dev/null || true

# ---- images/mirror.sh（与 WSL 上跑的是同一份）----
cat > $R/images/mirror.sh <<'MIRROR'
#!/bin/bash
# ============================================================
# skopeo 批量搬运镜像到 Harbor（amd64 单架构）
# 用法: bash mirror.sh [longhorn|logging|metrics|nfs|all]
# 运行环境: 需要能访问外网的机器（当前用 WSL），Harbor 走 NO_PROXY 直连
# ============================================================
export NO_PROXY='harbor.wuxing.local,10.100.10.29,localhost,127.0.0.1'
export no_proxy="$NO_PROXY"
H=harbor.wuxing.local; USER=admin; PASS='<HARBOR_PASSWORD>'
TARGET=${1:-all}
LIST_LONGHORN='
longhornio/longhorn-manager:v1.7.2|longhorn/longhorn-manager:v1.7.2
longhornio/longhorn-engine:v1.7.2|longhorn/longhorn-engine:v1.7.2
longhornio/longhorn-instance-manager:v1.7.2|longhorn/longhorn-instance-manager:v1.7.2
longhornio/longhorn-share-manager:v1.7.2|longhorn/longhorn-share-manager:v1.7.2
longhornio/longhorn-ui:v1.7.2|longhorn/longhorn-ui:v1.7.2
longhornio/backing-image-manager:v1.7.2|longhorn/backing-image-manager:v1.7.2
longhornio/support-bundle-kit:v0.0.45|longhorn/support-bundle-kit:v0.0.45
longhornio/csi-attacher:v4.7.0|longhorn/csi-attacher:v4.7.0
longhornio/csi-provisioner:v4.0.1-20241007|longhorn/csi-provisioner:v4.0.1-20241007
longhornio/csi-resizer:v1.12.0|longhorn/csi-resizer:v1.12.0
longhornio/csi-snapshotter:v7.0.2-20241007|longhorn/csi-snapshotter:v7.0.2-20241007
longhornio/csi-node-driver-registrar:v2.12.0|longhorn/csi-node-driver-registrar:v2.12.0
longhornio/livenessprobe:v2.14.0|longhorn/livenessprobe:v2.14.0
'
LIST_LOGGING='
grafana/loki:3.3.2|logging/loki:3.3.2
grafana/alloy:v1.7.0|logging/alloy:v1.7.0
'
LIST_METRICS='
registry.k8s.io/metrics-server/metrics-server:v0.7.2|metrics-server/metrics-server:v0.7.2
'
LIST_NFS='
registry.k8s.io/sig-storage/nfs-subdir-external-provisioner:v4.0.2|nfs-provisioner/nfs-subdir-external-provisioner:v4.0.2
'
case "$TARGET" in
  longhorn) LIST="$LIST_LONGHORN";; logging) LIST="$LIST_LOGGING";;
  metrics) LIST="$LIST_METRICS";; nfs) LIST="$LIST_NFS";;
  all) LIST="$LIST_LONGHORN$LIST_LOGGING$LIST_METRICS$LIST_NFS";;
  *) echo "用法: bash mirror.sh [longhorn|logging|metrics|nfs|all]"; exit 1;;
esac
for p in longhorn logging metrics-server nfs-provisioner; do
  curl -sk -o /dev/null -u "$USER:$PASS" -H 'Content-Type: application/json' \
    -X POST "https://$H/api/v2.0/projects" -d "{\"project_name\":\"$p\",\"public\":true}"
done
OK=0; FAIL=0
for line in $LIST; do
  [ -z "$line" ] && continue
  src="${line%%|*}"; dst="${line##*|}"
  if skopeo inspect --tls-verify=false --creds "$USER:$PASS" "docker://$H/$dst" >/dev/null 2>&1; then
    echo "  跳过(已存在) $dst"; OK=$((OK+1)); continue
  fi
  echo -n "  $src -> $dst ... "
  if skopeo copy --override-arch amd64 --override-os linux \
      --dest-tls-verify=false --dest-creds "$USER:$PASS" \
      "docker://$src" "docker://$H/$dst" >/dev/null 2>&1; then
    echo OK; OK=$((OK+1))
  else
    echo 失败; FAIL=$((FAIL+1))
  fi
done
echo "完成: 成功 $OK 失败 $FAIL"
MIRROR
chmod +x $R/images/mirror.sh

cat > $R/images/README.md <<'EOF'
# 镜像搬运（skopeo → Harbor）

## 为什么需要
集群内网无外网，所有镜像必须先在 Harbor 里。搬运机需要有外网的机器（当前用工作站的 WSL，已装 skopeo + regctl）。

## 怎么用
```bash
# 在 WSL 里执行（Harbor 走 NO_PROXY 直连，上游走代理）
bash mirror.sh all            # 全部
bash mirror.sh longhorn       # 只搬 Longhorn 的 13 个镜像
bash mirror.sh logging        # Loki + Alloy
bash mirror.sh metrics        # metrics-server
bash mirror.sh nfs            # NFS provisioner
```

## 镜像清单（脚本里维护，改这里即可）
| 组件 | 镜像数 | 说明 |
|---|---|---|
| longhorn | 13 | manager/engine/instance-manager/share-manager/ui/backing-image-manager + CSI sidecars |
| logging | 2 | loki:3.3.2 + alloy:v1.7.0 |
| metrics | 1 | metrics-server:v0.7.2 |
| nfs | 1 | nfs-subdir-external-provisioner:v4.0.2 |

## 单架构说明
用 `--override-arch amd64` 只搬 amd64（集群全是 amd64）。
**注意**：`--multi-arch all` 会带上用不到的冷门架构；`--multi-arch <平台列表>` 在 skopeo 1.24 有 bug（报 blob unknown），别用。

## 新增镜像时
1. 在 `mirror.sh` 对应清单里加一行：`上游镜像|Harbor项目/仓库:tag`
2. 重跑 `bash mirror.sh <组件>`
3. 在 `tools/fix-chart-images.py` 生成的 values 里确认目标仓库名对得上
EOF

# ---- logging ----
cat > $R/logging/README.md <<'EOF'
# 日志体系（Loki + Alloy）

## 为什么选这套
| 方案 | 评价 |
|---|---|
| **Loki + Alloy**（本方案） | ✅ 轻量（~200MB 内存）、Grafana 原生集成、只索引标签不索引全文 |
| EFK（Elasticsearch） | ❌ 太重（ES 至少 4G 内存），你这集群存储/网络吃紧 |
| 纯 kubectl logs | 只能看实时，不能跨 Pod 搜索、不能留存 |

架构：`Alloy(DaemonSet 采集) → Loki(存储+查询) → Grafana(展示)`

## 访问
- Grafana → Explore → 数据源选 `Loki`
- 或 Grafana → Dashboards 里的日志看板

## 关键 LogQL（怎么查日志）
```logql
# 某个命名空间的所有日志
{namespace="monitoring"}

# 某个 Pod 的日志
{namespace="kube-system", pod="cilium-xxxx"}

# 全文搜索错误（近似 grep）
{namespace="monitoring"} |= "error"

# 过滤 + 排除
{app="nginx"} |= "500" != "healthz"

# 统计错误速率（可做告警）
sum(rate({namespace="monitoring"} |= "error" [5m])) by (pod)

# JSON 日志解析
{app="myapp"} | json | level="error"
```

## 保留期与存储
- 默认保留 7 天（`01-loki.sh` 里 `retention_period`）
- 有共享存储后可挂 PVC；当前用 hostPath/emptyDir（按脚本设置）
EOF

cat > $R/logging/01-loki.sh <<'EOF'
#!/bin/bash
# 部署 Loki（SingleBinary 模式，轻量）
set -e
export KUBECONFIG=/etc/kubernetes/admin.conf
R=/data1/ssdxt; H=harbor.wuxing.local; NS=logging
kubectl create ns $NS --dry-run=client -o yaml | kubectl apply -f -

# 自动把所有镜像改写为 Harbor
python3 $R/tools/fix-chart-images.py $R/charts/loki-6.24.0.tgz logging $H /tmp/loki-values-harbor.yaml

cat > /tmp/loki-custom.yaml <<'YAML'
deploymentMode: SingleBinary
loki:
  auth_enabled: false
  commonConfig:
    replication_factor: 1
  storage:
    type: filesystem
  limits_config:
    retention_period: 168h          # 日志保留 7 天，改这里
    ingestion_rate_mb: 16
    ingestion_burst_size_mb: 32
  schemaConfig:
    configs:
    - from: "2024-01-01"
      store: tsdb
      object_store: filesystem
      schema: v13
      index: {prefix: loki_index_, period: 24h}
singleBinary:
  replicas: 1
  persistence:
    enabled: true
    size: 50Gi
    storageClass: longhorn        # 若还没装 Longhorn，改成 openebs-hostpath 或删掉这行用 emptyDir
  resources:
    requests: {cpu: 200m, memory: 512Mi}
    limits: {memory: 2Gi}
# 关掉用不到的重组件
backend: {replicas: 0}
read: {replicas: 0}
write: {replicas: 0}
gateway: {enabled: false}
chunksCache: {enabled: false}
resultsCache: {enabled: false}
lokiCanary: {enabled: false}
test: {enabled: false}
minio: {enabled: false}
YAML

helm upgrade --install loki $R/charts/loki-6.24.0.tgz -n $NS \
  -f /tmp/loki-values-harbor.yaml -f /tmp/loki-custom.yaml --timeout 15m 2>&1 | tail -5

echo ""
echo "验证: kubectl -n logging get pods"
echo "接入 Grafana: Grafana 会自动发现 Loki 数据源（若没有，手动加 http://loki-gateway.logging:80 或 http://loki.logging:3100）"
EOF

cat > $R/logging/02-alloy.sh <<'EOF'
#!/bin/bash
# 部署 Alloy（DaemonSet，采集所有节点/Pod 日志发给 Loki）
set -e
export KUBECONFIG=/etc/kubernetes/admin.conf
R=/data1/ssdxt; H=harbor.wuxing.local; NS=logging

python3 $R/tools/fix-chart-images.py $R/charts/alloy-0.12.0.tgz logging $H /tmp/alloy-values-harbor.yaml

# Alloy 配置：采集容器日志 → 推 Loki
cat > /tmp/alloy-custom.yaml <<'YAML'
alloy:
  configMap:
    create: true
    content: |
      // ---- 采集本节点所有容器日志 ----
      discovery.kubernetes "pods" {
        role = "pod"
      }
      discovery.relabel "pods" {
        rule {
          source_labels = ["__meta_kubernetes_pod_name"]
          target_label  = "pod"
        }
        rule {
          source_labels = ["__meta_kubernetes_namespace"]
          target_label  = "namespace"
        }
        rule {
          source_labels = ["__meta_kubernetes_pod_container_name"]
          target_label  = "container"
        }
        rule {
          source_labels = ["__meta_kubernetes_pod_node_name"]
          target_label  = "node"
        }
      }
      loki.source.kubernetes "pods" {
        targets    = discovery.relabel.pods.output
        forward_to = [loki.write.default.receiver]
      }
      loki.write "default" {
        endpoint {
          url = "http://loki.logging.svc.cluster.local:3100/loki/api/v1/push"
        }
      }
  resources:
    requests: {cpu: 100m, memory: 256Mi}
    limits: {memory: 1Gi}
controller:
  type: daemonset
  tolerations:
  - operator: Exists
configReloader:
  enabled: false
YAML

helm upgrade --install alloy $R/charts/alloy-0.12.0.tgz -n $NS \
  -f /tmp/alloy-values-harbor.yaml -f /tmp/alloy-custom.yaml --timeout 15m 2>&1 | tail -5

echo ""
echo "验证:"
echo "  kubectl -n logging get ds alloy"
echo "  在 Grafana Explore 里查: {namespace=\"monitoring\"}"
EOF

# ---- gateway ----
cat > $R/gateway/README.md <<'EOF'
# Gateway API 对外暴露（持久化方案，不用 nohup）

## 原理
```
浏览器 → grafana.wuxing.local
           ↓ DNS/hosts
        10.100.10.x  ← kube-vip 分配给 Gateway 的 LoadBalancer IP
           ↓
        Cilium Gateway（gatewayClassName: cilium）
           ↓ HTTPRoute 按域名分流
   ┌───────────┬──────────────┬───────────────┐
   Grafana    Prometheus    Alertmanager    Longhorn UI
```

**为什么不用端口转发**：`kubectl port-forward` 是进程级的，SSH 一断就没；Gateway 是集群对象，**重启、换机器都还在**。

## 域名规划（改 `01-deploy.sh` 里的列表即可）
| 域名 | 后端 |
|---|---|
| `grafana.wuxing.local` | Grafana:3000 |
| `prometheus.wuxing.local` | Prometheus:9090 |
| `alertmanager.wuxing.local` | Alertmanager:9093 |
| `longhorn.wuxing.local` | Longhorn UI:80 |

## 客户端要做的
在**访问者的机器**上加 hosts（或用内部 DNS）：
```
10.100.10.40  grafana.wuxing.local prometheus.wuxing.local alertmanager.wuxing.local longhorn.wuxing.local
```
（IP 用 `kubectl get gateway -A` 查到的实际 LB IP）

## 常用命令
```bash
kubectl get gateway -A                     # 看网关和它的 IP
kubectl get httproute -A                   # 看路由
kubectl describe gateway -n gateway monitoring-gateway   # 排障
```

## 想加 HTTPS
cert-manager 已装。给 Gateway 加 listener（443）+ 自签 ClusterIssuer 即可，见 `01-deploy.sh` 末尾注释。
EOF

cat > $R/gateway/01-deploy.sh <<'EOF'
#!/bin/bash
# 部署 Gateway + HTTPRoute，把监控/存储界面用域名暴露（持久化）
set -e
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=gateway
kubectl create ns $NS --dry-run=client -o yaml | kubectl apply -f -

echo "=== [1/3] 部署 Gateway（kube-vip 会给它分配 LoadBalancer IP）==="
cat <<'YAML' | kubectl apply -f -
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: monitoring-gateway
  namespace: gateway
spec:
  gatewayClassName: cilium
  listeners:
  - name: http
    protocol: HTTP
    port: 80
    allowedRoutes:
      namespaces:
        from: All
YAML

echo "=== [2/3] 在各命名空间建服务别名（Gateway 不能跨命名空间引 Service，用 ReferenceGrant 或同 ns 服务）==="
# 在 gateway 命名空间建 ExternalName 服务指向各后端
for pair in "grafana:prometheus-stack-grafana.monitoring:80" \
            "prometheus:prometheus-stack-kube-prom-prometheus.monitoring:9090" \
            "alertmanager:prometheus-stack-kube-prom-alertmanager.monitoring:9093" \
            "longhorn:longhorn-frontend.longhorn-system:80"; do
  name="${pair%%:*}"; rest="${pair#*:}"; svc="${rest%%:*}"; port="${rest##*:}"
  cat <<YAML | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: $name
  namespace: $NS
spec:
  type: ExternalName
  externalName: $svc
  ports:
  - port: $port
YAML
done

echo "=== [3/3] 部署 HTTPRoute（按域名分流）==="
cat <<'YAML' | kubectl apply -f -
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: monitoring-routes
  namespace: gateway
spec:
  parentRefs:
  - name: monitoring-gateway
  rules:
  - matches: [{path: {type: PathPrefix, value: /}}]
    backendRefs:
    - {name: grafana, port: 80}
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: prometheus-route
  namespace: gateway
spec:
  parentRefs: [{name: monitoring-gateway}]
  hostnames: ["prometheus.wuxing.local"]
  rules:
  - matches: [{path: {type: PathPrefix, value: /}}]
    backendRefs: [{name: prometheus, port: 9090}]
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: alertmanager-route
  namespace: gateway
spec:
  parentRefs: [{name: monitoring-gateway}]
  hostnames: ["alertmanager.wuxing.local"]
  rules:
  - matches: [{path: {type: PathPrefix, value: /}}]
    backendRefs: [{name: alertmanager, port: 9093}]
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: longhorn-route
  namespace: gateway
spec:
  parentRefs: [{name: monitoring-gateway}]
  hostnames: ["longhorn.wuxing.local"]
  rules:
  - matches: [{path: {type: PathPrefix, value: /}}]
    backendRefs: [{name: longhorn, port: 80}]
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: grafana-route
  namespace: gateway
spec:
  parentRefs: [{name: monitoring-gateway}]
  hostnames: ["grafana.wuxing.local"]
  rules:
  - matches: [{path: {type: PathPrefix, value: /}}]
    backendRefs: [{name: grafana, port: 80}]
YAML

echo ""
echo "=== 等 30 秒看 LB IP ==="
sleep 30
kubectl get gateway -n $NS
GWIP=$(kubectl get gateway monitoring-gateway -n $NS -o jsonpath='{.status.addresses[0].value}' 2>/dev/null)
echo ""
echo "Gateway IP: ${GWIP:-未分配（检查 kube-vip svc_enable 是否为 true）}"
echo ""
echo "在访问者机器上加 hosts:"
echo "  ${GWIP:-<IP>}  grafana.wuxing.local prometheus.wuxing.local alertmanager.wuxing.local longhorn.wuxing.local"
echo ""
echo "注: HTTPS 需要给 Gateway 加 443 listener + cert-manager 证书，见 README"
EOF
chmod +x $R/gateway/01-deploy.sh $R/logging/*.sh $R/storage/*.sh $R/monitoring/*.sh

echo "=== 最终目录树 ==="
cd $R && find . -maxdepth 2 \( -name '*.sh' -o -name '*.md' -o -name '*.py' \) | sort | sed 's/^\.\///' | awk '{printf "  %s\n", $0}'
