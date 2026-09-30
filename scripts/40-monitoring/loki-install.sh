#!/bin/bash
# 部署 Loki（SingleBinary 模式，轻量）
set -e
export KUBECONFIG=/etc/kubernetes/admin.conf
R=/data1/ssdxt; H=harbor.wuxing.local; NS=logging
kubectl create ns $NS --dry-run=client -o yaml | kubectl apply -f -

# 日志告警规则 ConfigMap（2026-09-30 ruler 落地）
kubectl apply -f $R/logging/loki-ruler-rules.yaml

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
  -f /tmp/loki-values-harbor.yaml -f /tmp/loki-custom.yaml -f $R/values/loki-ruler.yaml --timeout 15m 2>&1 | tail -5

echo ""
echo "验证: kubectl -n logging get pods"
echo "接入 Grafana: Grafana 会自动发现 Loki 数据源（若没有，手动加 http://loki-gateway.logging:80 或 http://loki.logging:3100）"
