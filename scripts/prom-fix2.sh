#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
H=harbor.wuxing.local
helm upgrade prometheus-stack /data1/ssdxt/charts/kube-prometheus-stack-62.7.0.tgz -n monitoring --reuse-values \
  --set prometheus.prometheusSpec.image.registry=$H \
  --set prometheus.prometheusSpec.image.repository=monitoring/prometheus \
  --set prometheus.prometheusSpec.image.tag=v2.54.1 \
  --set alertmanager.alertmanagerSpec.image.registry=$H \
  --set alertmanager.alertmanagerSpec.image.repository=monitoring/alertmanager \
  --set alertmanager.alertmanagerSpec.image.tag=v0.27.0 \
  --timeout 10m 2>&1 | tail -2
echo "=== 验证镜像"
sleep 20
kubectl get pod prometheus-prometheus-stack-kube-prom-prometheus-0 -n monitoring -o jsonpath='{.spec.containers[0].image}' 2>&1; echo
kubectl get pod alertmanager-prometheus-stack-kube-prom-alertmanager-0 -n monitoring -o jsonpath='{.spec.containers[0].image}' 2>&1; echo
echo "=== 等 200 秒"
sleep 200
echo "=== monitoring 最终状态"
kubectl get pods -n monitoring --no-headers 2>&1 | awk '{print $1, $2, $3}' | grep -v node-exporter