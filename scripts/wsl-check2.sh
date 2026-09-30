#!/bin/bash
cd /mnt/c/Users/CC/Desktop/dsh
{
echo "== pull脚本是否在跑"
pgrep -f wsl-pull-images >/dev/null && echo RUNNING || echo STOPPED
echo "== 目标镜像检查"
for i in quay.io/prometheus-operator/prometheus-operator:v0.76.1 quay.io/prometheus/prometheus:v2.54.1 quay.io/prometheus/alertmanager:v0.27.0 docker.io/grafana/grafana:11.2.0 quay.io/prometheus/node-exporter:v1.8.2 registry.k8s.io/kube-state-metrics/kube-state-metrics:v2.13.0 quay.io/kiwigrid/k8s-sidecar:1.27.4 quay.io/jetstack/cert-manager-controller:v1.16.1 quay.io/jetstack/cert-manager-cainjector:v1.16.1 quay.io/jetstack/cert-manager-webhook:v1.16.1 quay.io/jetstack/cert-manager-startupapicheck:v1.16.1; do
  docker image inspect "$i" >/dev/null 2>&1 && echo "OK  $i" || echo "MISS $i"
done
} > pull-check.txt 2>&1