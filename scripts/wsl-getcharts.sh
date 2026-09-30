#!/bin/bash
# 在工作站 WSL 下载缺失的 helm chart（longhorn / loki / alloy），放到 /tmp/charts
set -u
OUT=/tmp/dsh-charts
mkdir -p $OUT
cd $OUT

echo "=== helm repo list (before) ==="
helm repo list 2>&1

echo "=== add repos ==="
helm repo add longhorn https://charts.longhorn.io 2>&1 | tail -2
helm repo add grafana https://grafana.github.io/helm-charts 2>&1 | tail -2
helm repo update 2>&1 | tail -5

echo "=== pull longhorn 1.7.2 ==="
helm pull longhorn/longhorn --version 1.7.2 -d $OUT 2>&1 | tail -3
echo "=== pull loki 6.24.0 ==="
helm pull grafana/loki --version 6.24.0 -d $OUT 2>&1 | tail -3
echo "=== pull alloy 0.12.0 ==="
helm pull grafana/alloy --version 0.12.0 -d $OUT 2>&1 | tail -3

echo "=== result ==="
ls -la $OUT
