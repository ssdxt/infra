#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "========== 1. 全集群验证 =========="
kubectl get nodes --no-headers 2>&1 | awk '{print $2}' | sort | uniq -c
echo "--- 非Running"
kubectl get pods -A --no-headers 2>/dev/null | grep -v -E 'Running|Completed' | head -5 || echo ALL-RUNNING
echo "--- gatewayclass"
kubectl get gatewayclass 2>&1 | tail -1
echo "========== 2. 安装 kube-prometheus-stack =========="
helm install prometheus-stack /data1/ssdxt/charts/kube-prometheus-stack-62.7.0.tgz \
  -n monitoring --create-namespace \
  --set prometheusOperator.admissionWebhooks.enabled=false \
  --set prometheusOperator.image.repository=harbor.wuxing.local/monitoring/prometheus-operator \
  --set prometheusOperator.image.tag=v0.76.1 \
  --set prometheusOperator.prometheusConfigReloader.image.repository=harbor.wuxing.local/monitoring/prometheus-operator \
  --set prometheusOperator.prometheusConfigReloader.image.tag=v0.76.1 \
  --set prometheus.image.repository=harbor.wuxing.local/monitoring/prometheus \
  --set prometheus.image.tag=v2.54.1 \
  --set alertmanager.image.repository=harbor.wuxing.local/monitoring/alertmanager \
  --set alertmanager.image.tag=v0.27.0 \
  --set grafana.image.repository=harbor.wuxing.local/monitoring/grafana \
  --set grafana.image.tag=11.2.0 \
  --set grafana.initChownData.image.repository=harbor.wuxing.local/library/busybox \
  --set grafana.sidecar.image.repository=harbor.wuxing.local/monitoring/k8s-sidecar \
  --set grafana.sidecar.image.tag=1.27.4 \
  --set prometheus-node-exporter.image.repository=harbor.wuxing.local/monitoring/node-exporter \
  --set prometheus-node-exporter.image.tag=v1.8.2 \
  --set kube-state-metrics.image.repository=harbor.wuxing.local/monitoring/kube-state-metrics \
  --set kube-state-metrics.image.tag=v2.13.0 \
  --timeout 15m 2>&1 | tail -4
echo "=== 等待 150 秒"
sleep 150
echo "========== 3. monitoring 命名空间状态 =========="
kubectl get pods -n monitoring --no-headers 2>&1 | awk '{print $1, $2, $3}' | head -15