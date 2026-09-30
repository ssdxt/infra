#!/bin/bash
set -e
export no_proxy='10.100.10.0/24,harbor.wuxing.local,localhost,127.0.0.1'
export NO_PROXY='10.100.10.0/24,harbor.wuxing.local,localhost,127.0.0.1'
mkdir -p /home/cc/offline-images
cd /home/cc/offline-images
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
for img in "${IMGS[@]}"; do
  name=$(echo $img | tr '/:' '__')
  echo "== pull $img"
  docker pull "$img" >/dev/null 2>&1 && echo "  pulled" || echo "  PULL FAIL"
done
echo "== save all to one tar"
docker save $(docker images --format '{{.Repository}}:{{.Tag}}' | grep -E 'prometheus|grafana|node-exporter|kube-state|sidecar|cert-manager' | grep -v 'alpine') -o /home/cc/offline-images/all-images.tar 2>&1 | tail -2
ls -lh /home/cc/offline-images/all-images.tar
echo "ALLDONE"