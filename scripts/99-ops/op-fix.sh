#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
helm upgrade prometheus-stack /data1/ssdxt/charts/kube-prometheus-stack-62.7.0.tgz -n monitoring --reuse-values \
  --set prometheusOperator.tls.enabled=false \
  --timeout 10m 2>&1 | tail -2
echo "=== 清理卡住的旧 Pod"
kubectl delete pods -n monitoring --field-selector status.phase!=Running --force --grace-period=0 2>&1 | tail -2
echo "=== 等 150 秒"
sleep 150
echo "=== monitoring 全部 Pod"
kubectl get pods -n monitoring --no-headers 2>&1 | awk '{print $1, $2, $3}' | grep -v node-exporter
echo "=== StatefulSet（Prometheus/Alertmanager）"
kubectl get statefulset -n monitoring --no-headers 2>&1 | awk '{print $1, $2}'