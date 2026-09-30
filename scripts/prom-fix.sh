#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
H=harbor.wuxing.local
helm upgrade prometheus-stack /data1/ssdxt/charts/kube-prometheus-stack-62.7.0.tgz -n monitoring --reuse-values \
  --set prometheusOperator.prometheusConfigReloader.image.registry=$H \
  --set prometheusOperator.prometheusConfigReloader.image.repository=monitoring/prometheus-config-reloader \
  --set prometheusOperator.prometheusConfigReloader.image.tag=v0.76.1 \
  --timeout 10m 2>&1 | tail -2
echo "=== 清理失败 Pod"
kubectl delete pods -n monitoring prometheus-prometheus-stack-kube-prom-prometheus-0 alertmanager-prometheus-stack-kube-prom-alertmanager-0 --force --grace-period=0 2>&1 | tail -2
echo "=== 等 180 秒"
sleep 180
echo "=== monitoring 全部 Pod（除 node-exporter）"
kubectl get pods -n monitoring --no-headers 2>&1 | awk '{print $1, $2, $3}' | grep -v node-exporter