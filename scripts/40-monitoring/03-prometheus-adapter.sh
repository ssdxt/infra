#!/bin/bash
# 03-prometheus-adapter.sh - idempotent install of prometheus-adapter (offline, image from Harbor)
set -euo pipefail
CHART=/data1/ssdxt/charts/prometheus-adapter-5.3.0.tgz
VALUES=/data1/ssdxt/values/prometheus-adapter-values.yaml
export KUBECONFIG=/etc/kubernetes/admin.conf

echo "== precheck =="
kubectl get ns monitoring >/dev/null
kubectl -n monitoring get svc prometheus-stack-kube-prom-prometheus >/dev/null
echo "precheck OK"

echo "== install/upgrade =="
helm upgrade --install prometheus-adapter "$CHART" -n monitoring -f "$VALUES"

echo "== wait =="
kubectl -n monitoring rollout status deploy/prometheus-adapter --timeout=300s

echo "== verify =="
kubectl -n monitoring get pods -l app.kubernetes.io/name=prometheus-adapter
kubectl get apiservice v1beta1.custom.metrics.k8s.io
kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1 | head -c 800; echo