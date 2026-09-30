#!/bin/bash
# 04-etcd-monitoring.sh — etcd 监控打通（方案①：静态 Endpoints + mTLS）
# 背景：etcd 为 systemd 服务（kk 安装形态），chart 自带 Service/SM 匹配 0 Pod；2379 强制 mTLS。
# 幂等：重跑不炸；改动前备份。不碰 etcd 本身。
set -euo pipefail
TS=$(date +%m%d-%H%M%S)

echo "=== [1/4] 备份 etcd 客户端证书 + 创建 Secret（ns monitoring）==="
mkdir -p /data1/ssdxt/monitoring/backup/etcd-certs
cp -a /etc/kubernetes/pki/etcd/ca.crt /etc/kubernetes/pki/etcd/client.crt /etc/kubernetes/pki/etcd/client.key \
      /data1/ssdxt/monitoring/backup/etcd-certs/
kubectl -n monitoring create secret generic kube-etcd-client-certs \
  --from-file=ca.crt=/etc/kubernetes/pki/etcd/ca.crt \
  --from-file=client.crt=/etc/kubernetes/pki/etcd/client.crt \
  --from-file=client.key=/etc/kubernetes/pki/etcd/client.key \
  --dry-run=client -o yaml | kubectl apply -f -

echo "=== [2/4] 应用 Service + Endpoints + ServiceMonitor ==="
kubectl apply -f /data1/ssdxt/monitoring/manifests/04-etcd-monitoring.yaml

echo "=== [3/4] 确认 Prometheus CR 挂了证书 Secret（secrets 已固化进 values，勿只靠本检查）==="
CUR=$(kubectl -n monitoring get prometheus prometheus-stack-kube-prom-prometheus -o jsonpath='{.spec.secrets}' 2>/dev/null || echo '[]')
echo "secrets=$CUR"
if ! echo "$CUR" | grep -q kube-etcd-client-certs; then
  echo "!! secrets 字段缺失，用 kubectl patch 兜底（helm upgrade 后必须改 values 重固化）："
  kubectl -n monitoring patch prometheus prometheus-stack-kube-prom-prometheus --type=merge \
    -p '{"spec":{"secrets":["kube-etcd-client-certs"]}}'
  kubectl -n monitoring wait --for=condition=Ready pod/prometheus-prometheus-stack-kube-prom-prometheus-0 --timeout=300s
fi

echo "=== [4/4] 验证 ==="
sleep 20
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- \
  wget -qO- 'http://localhost:9090/api/v1/query?query=up%7Bjob%3D%22kube-etcd%22%7D' | head -c 600; echo
echo "期望：3 条 series 且 value=1。fsync p99 查询："
echo "histogram_quantile(0.99, sum(rate(etcd_disk_wal_fsync_duration_seconds_bucket[5m])) by (instance,le))"