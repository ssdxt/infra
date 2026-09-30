#!/bin/bash
# ============================================================
# 01-install-tetragon.sh —— Tetragon 1.7.1 离线安装（幂等）
# 在 control-01 执行；KUBECONFIG 已在 root 环境指向 admin.conf
# 依赖：/data1/ssdxt/charts/tetragon-1.7.1.tgz
#       /data1/ssdxt/security/tetragon-values.yaml
#       /data1/ssdxt/security/policies-baseline.yaml
#       /data1/ssdxt/security/tetragon-dashboard-cm.yaml
# 镜像：harbor.wuxing.local/tetragon/*（显式 tag，无 digest）
# ============================================================
set -euo pipefail

CHART=/data1/ssdxt/charts/tetragon-1.7.1.tgz
VALUES=/data1/ssdxt/security/tetragon-values.yaml
POLICIES=/data1/ssdxt/security/policies-baseline.yaml
DASH=/data1/ssdxt/security/tetragon-dashboard-cm.yaml
NS=tetragon
TS=$(date +%Y%m%d)

[ -f "$CHART" ]    || { echo "缺少 $CHART";    exit 1; }
[ -f "$VALUES" ]   || { echo "缺少 $VALUES";   exit 1; }
[ -f "$POLICIES" ] || { echo "缺少 $POLICIES"; exit 1; }

echo "== [1/4] helm install/upgrade tetragon"
# 幂等：已存在则 upgrade，不存在则 install
if helm status tetragon -n "$NS" >/dev/null 2>&1; then
  helm upgrade tetragon "$CHART" -n "$NS" -f "$VALUES"
else
  helm install tetragon "$CHART" -n "$NS" --create-namespace -f "$VALUES"
fi

echo "== [2/4] 等待 Deployment/DaemonSet 就绪"
kubectl -n "$NS" rollout status deploy/tetragon-operator --timeout=300s || true
kubectl -n "$NS" rollout status ds/tetragon --timeout=300s

echo "== [3/4] 应用基线安全策略（已有同名策略则覆盖，自动备份到 *.bak.$TS）"
kubectl apply -f "$POLICIES"

echo "== [4/4] 导入 Grafana 看板 ConfigMap（label grafana_dashboard=1）"
if kubectl -n "$NS" get cm tetragon-dashboard >/dev/null 2>&1 && [ -f "$DASH" ]; then
  kubectl -n "$NS" get cm tetragon-dashboard -o yaml > "${DASH}.cm.bak.$TS"
fi
[ -f "$DASH" ] && kubectl apply -f "$DASH" || echo "跳过看板：未找到 $DASH"

echo "== 完成。验证："
kubectl -n "$NS" get pods -o wide
kubectl -n "$NS" get tracingpolicies.cilium.io,tracingpoliciesnamespaced.cilium.io -A
