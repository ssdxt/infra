#!/bin/bash
mkdir -p /mnt/e/ZP-工作信息/infra-tool-ssdxt/kubernetes/kubekey/oneclick/offline
cd /mnt/e/ZP-工作信息/infra-tool-ssdxt/kubernetes/kubekey/oneclick/offline
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
echo "== save all to one tar"
docker save "${IMGS[@]}" -o all-images.tar 2>&1 | tail -1
ls -lh all-images.tar
echo SAVED