#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
H=harbor.wuxing.local
helm upgrade prometheus-stack /data1/ssdxt/charts/kube-prometheus-stack-62.7.0.tgz \
  -n monitoring --reuse-values \
  --set prometheusOperator.image.registry=$H --set prometheusOperator.image.repository=monitoring/prometheus-operator --set prometheusOperator.image.tag=v0.76.1 \
  --set prometheusOperator.prometheusConfigReloader.image.registry=$H --set prometheusOperator.prometheusConfigReloader.image.repository=monitoring/prometheus-operator --set prometheusOperator.prometheusConfigReloader.image.tag=v0.76.1 \
  --set prometheus.image.registry=$H --set prometheus.image.repository=monitoring/prometheus --set prometheus.image.tag=v2.54.1 \
  --set alertmanager.image.registry=$H --set alertmanager.image.repository=monitoring/alertmanager --set alertmanager.image.tag=v0.27.0 \
  --set grafana.image.registry=$H --set grafana.image.repository=monitoring/grafana --set grafana.image.tag=11.2.0 \
  --set grafana.initChownData.image.registry=$H --set grafana.initChownData.image.repository=library/busybox --set grafana.initChownData.image.tag=1.38.0 \
  --set grafana.sidecar.image.registry=$H --set grafana.sidecar.image.repository=monitoring/k8s-sidecar --set grafana.sidecar.image.tag=1.27.4 \
  --set prometheus-node-exporter.image.registry=$H --set prometheus-node-exporter.image.repository=monitoring/node-exporter --set prometheus-node-exporter.image.tag=v1.8.2 \
  --set kube-state-metrics.image.registry=$H --set kube-state-metrics.image.repository=monitoring/kube-state-metrics --set kube-state-metrics.image.tag=v2.13.0 \
  --timeout 15m 2>&1 | tail -3
echo "=== 验证镜像路径"
sleep 20
kubectl get ds prometheus-stack-prometheus-node-exporter -n monitoring -o jsonpath='{.spec.template.spec.containers[0].image}' 2>&1; echo
kubectl get deploy prometheus-stack-kube-state-metrics -n monitoring -o jsonpath='{.spec.template.spec.containers[0].image}' 2>&1; echo
echo "=== 等 150 秒"
sleep 150
kubectl get pods -n monitoring --no-headers 2>&1 | awk '{print $1, $2, $3}' | head -18