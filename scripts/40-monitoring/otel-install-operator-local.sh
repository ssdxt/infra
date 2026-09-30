#!/bin/bash
# 幂等安装 OpenTelemetry Operator（离线，chart+镜像均已本地化）
# chart: /data1/ssdxt/charts/opentelemetry-operator-0.123.1.tgz (app version 0.159.0)
# 镜像: harbor.wuxing.local/otel/*
# 前置: cert-manager 已安装 (1.16.1)，operator webhook 证书由其签发
set -e
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
CHART=/data1/ssdxt/charts/opentelemetry-operator-0.123.1.tgz
NS=opentelemetry-operator-system
VALUES=$SCRIPT_DIR/otel-values.yaml

export KUBECONFIG=/etc/kubernetes/admin.conf

# 前置检查：cert-manager 必须先就绪（operator webhook 证书依赖它）
if ! kubectl get deployment -n cert-manager cert-manager-webhook >/dev/null 2>&1; then
  echo "ERROR: cert-manager 未安装，先装 cert-manager 再装本 operator"; exit 1
fi

if helm status opentelemetry-operator -n $NS >/dev/null 2>&1; then
  echo "== 已存在，执行 helm upgrade（幂等）"
  helm upgrade opentelemetry-operator "$CHART" -n $NS -f "$VALUES"
else
  echo "== 首次安装"
  helm install opentelemetry-operator "$CHART" -n $NS --create-namespace -f "$VALUES"
fi

# 【关键】若 operator 曾在 feature gate 开启期间运行过，会残留它自建的 NetworkPolicy
# （egress 只放行 apiserver 真实 IP:6443，operator 连不上 10.233.0.1 必挂），必须删除
kubectl delete netpol -n $NS opentelemetry-operator --ignore-not-found=true
kubectl delete netpol -n $NS smoke-collector-networkpolicy --ignore-not-found=true

kubectl -n $NS rollout status deployment/opentelemetry-operator --timeout=300s
kubectl get crd | grep opentelemetry
echo "== 安装完成"
