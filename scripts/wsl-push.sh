#!/bin/bash
set -e
H=harbor.wuxing.local
HU=admin
HP=<HARBOR_PASSWORD>
echo "== 建 Harbor 项目"
for p in monitoring cert-manager gateway; do
  code=$(curl -sk -o /dev/null -w '%{http_code}' -u $HU:$HP -H "Content-Type: application/json" -X POST "https://$H/api/v2.0/projects" -d "{\"project_name\":\"$p\",\"public\":true}")
  echo "  project $p -> $code (201=新建,409=已存在)"
done
echo "== docker login"
echo "$HP" | docker login $H -u $HU --password-stdin 2>&1 | tail -1
echo "== 拉取+推送 kube-prometheus-stack 镜像"
declare -A M1=(
  [quay.io/prometheus-operator/prometheus-operator:v0.76.1]=monitoring/prometheus-operator
  [quay.io/prometheus/prometheus:v2.54.1]=monitoring/prometheus
  [quay.io/prometheus/alertmanager:v0.27.0]=monitoring/alertmanager
  [docker.io/grafana/grafana:11.2.0]=monitoring/grafana
  [quay.io/prometheus/node-exporter:v1.8.2]=monitoring/node-exporter
  [registry.k8s.io/kube-state-metrics/kube-state-metrics:v2.13.0]=monitoring/kube-state-metrics
  [quay.io/kiwigrid/k8s-sidecar:1.27.4]=monitoring/k8s-sidecar
)
for src in "${!M1[@]}"; do
  dst="${M1[$src]}"
  echo "  pull $src"
  docker pull "$src" >/dev/null 2>&1 || { echo "  FAIL pull $src"; continue; }
  docker tag "$src" "$H/$dst"
  docker push "$H/$dst" >/dev/null 2>&1 && echo "  pushed $H/$dst" || echo "  FAIL push $H/$dst"
done
echo "== 拉取+推送 cert-manager 镜像"
for img in controller cainjector webhook startupapicheck; do
  src="quay.io/jetstack/cert-manager-$img:v1.16.1"
  echo "  pull $src"
  docker pull "$src" >/dev/null 2>&1 || { echo "  FAIL pull $src"; continue; }
  docker tag "$src" "$H/cert-manager/cert-manager-$img:v1.16.1"
  docker push "$H/cert-manager/cert-manager-$img:v1.16.1" >/dev/null 2>&1 && echo "  pushed $H/cert-manager/cert-manager-$img:v1.16.1" || echo "  FAIL push"
done
echo "DONE"