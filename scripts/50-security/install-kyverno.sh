#!/bin/bash
# kyverno 离线安装脚本（幂等）—— control-01 上执行
set -euo pipefail
export KUBECONFIG=/etc/kubernetes/admin.conf
CHART=/data1/ssdxt/charts/kyverno-3.9.1.tgz
VALUES=/data1/ssdxt/security/kyverno/values.yaml
POLICY=/data1/ssdxt/security/kyverno/inject-proxy-policy.yaml
TS=$(date +%Y%m%d)

# 备份旧资产
for f in "$VALUES" "$POLICY"; do
  [ -f "$f" ] && cp -a "$f" "$f.bak.$TS" || true
done

# 1. 安装/升级 kyverno
helm upgrade --install kyverno "$CHART" -n kyverno --create-namespace \
  -f "$VALUES" --timeout 10m

kubectl -n kyverno rollout status deploy/kyverno-admission-controller --timeout=300s
kubectl -n kyverno rollout status deploy/kyverno-cleanup-controller --timeout=300s || true
kubectl get pods -n kyverno

# 2. 应用代理注入策略（已存在则替换）
kubectl apply -f "$POLICY"
sleep 3
kubectl get cpol inject-proxy-env -o wide
kubectl get cpol inject-proxy-env -o jsonpath='{.status.ready}{"\n"}'
