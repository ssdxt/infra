#!/bin/bash
export no_proxy='10.100.10.0/24,harbor.wuxing.local,localhost,127.0.0.1'
export NO_PROXY='10.100.10.0/24,harbor.wuxing.local,localhost,127.0.0.1'
declare -a IMGS=(
  "quay.io/prometheus-operator/prometheus-operator:v0.76.1"
  "quay.io/prometheus/prometheus:v2.54.1"
  "quay.io/prometheus/alertmanager:v0.27.0"
  "docker.io/grafana/grafana:11.2.0"
  "quay.io/prometheus/node-exporter:v1.8.2"
  "registry.k8s.io/kube-state-metrics/kube-state-metrics:v2.13.0"
  "quay.io/kiwigrid/k8s-sidecar:1.27.4"
  "quay.io/jetstack/cert-manager-controller:v1.16.1"
  "quay.io/jetstack/cert-manager-cainjector:v1.16.1"
  "quay.io/jetstack/cert-manager-webhook:v1.16.1"
  "quay.io/jetstack/cert-manager-startupapicheck:v1.16.1"
)
OK=0; FAIL=0
for img in "${IMGS[@]}"; do
  echo "== pull $img"
  if docker pull "$img" >/dev/null 2>&1; then echo "  OK"; OK=$((OK+1)); else echo "  FAIL"; FAIL=$((FAIL+1)); fi
done
echo "SUMMARY ok=$OK fail=$FAIL"