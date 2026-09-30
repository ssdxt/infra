#!/bin/bash
cd /data1/ssdxt/charts/gateway-api
echo "=== 目录里的文件与大小"
ls -la
echo ""
echo "=== 每个文件自带的版本标识（关键证据）"
for f in *.yaml; do
  v=$(grep -m1 -E 'gateway.networking.k8s.io/bundle-version|app.kubernetes.io/version' "$f" 2>/dev/null | tr -d ' ')
  n=$(grep -c '^kind: CustomResourceDefinition' "$f" 2>/dev/null)
  echo "  $f"
  echo "     版本标识: ${v:-未标注}"
  echo "     含CRD数量: $n"
done
echo ""
echo "=== 那 5 个单文件各自含哪些 CRD"
for f in gateway.networking.k8s.io_*.yaml; do
  echo -n "  $f -> "
  grep -m1 '^  name: ' "$f" 2>/dev/null | awk '{print $2}'
done