#!/bin/bash
# 05-install-keda.sh — 离线安装 KEDA 2.21.0（幂等），Prometheus 触发伸缩演示样例
# 前置：/data1/ssdxt/charts/keda-2.21.0.tgz、/data1/ssdxt/values/keda-values.yaml、
#       /data1/ssdxt/monitoring/manifests/keda-demo.yaml 均已就位
set -euo pipefail
TS=$(date +%Y%m%d)
CHART=/data1/ssdxt/charts/keda-2.21.0.tgz
VALUES=/data1/ssdxt/values/keda-values.yaml
DEMO=/data1/ssdxt/monitoring/manifests/keda-demo.yaml

for f in "$CHART" "$VALUES" "$DEMO"; do
  [ -f "$f" ] || { echo "缺少 $f"; exit 1; }
done

echo "=== 1. helm upgrade --install keda"
helm upgrade --install keda "$CHART" -n keda --create-namespace -f "$VALUES" --timeout 10m

echo "=== 2. 等待 keda 命名空间就绪"
kubectl -n keda rollout status deploy/keda-operator  --timeout=300s
kubectl -n keda rollout status deploy/keda-operator-metrics-apiserver --timeout=300s
kubectl -n keda rollout status deploy/keda-admission-webhooks --timeout=300s || true

echo "=== 3. APIService 检查"
kubectl wait --for=condition=Available apiservice/v1beta1.external.metrics.k8s.io --timeout=300s
kubectl get apiservice v1beta1.external.metrics.k8s.io

echo "=== 4. 部署演示样例（幂等 apply；保留作为活样例）"
kubectl apply -f "$DEMO"
kubectl -n keda-demo rollout status deploy/demo-nginx --timeout=300s || true

echo "=== 5. 验证"
sleep 30
kubectl get pods -n keda
kubectl -n keda-demo get scaledobject demo-prom
kubectl get apiservice v1beta1.external.metrics.k8s.io
kubectl get --raw "/apis/external.metrics.k8s.io/v1beta1/namespaces/keda-demo/s0-prometheus?labelSelector=scaledobject.keda.sh%2Fname%3Ddemo-prom" || true
echo "=== 完成"
