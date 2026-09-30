#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=monitoring; PROM=prometheus-stack-kube-prom-prometheus; CP=prometheus-$PROM-0
P=http://127.0.0.1:9091

echo "===== [1] config_out 里 remote_write 段的精确定义 ====="
kubectl -n $NS exec $CP -c prometheus -- sh -c \
  'awk "/^remote_write:/{f=1} f{print} f&&/^[a-z_]+:/&&!/^remote_write:/{exit}" /etc/prometheus/config_out/prometheus.env.yaml' 2>&1 | head -30

echo
echo "===== [2] 是否含第 4 条(ALERTS|count:up) ====="
kubectl -n $NS exec $CP -c prometheus -- sh -c \
  'sed -n "/^remote_write:/,/^[a-z_]\+:/p" /etc/prometheus/config_out/prometheus.env.yaml | grep -c "ALERTS"' 2>&1 \
  | sed 's/^/  匹配 ALERTS 的行数 = /'

echo
echo "===== [3] 热加载时间点 ====="
kubectl -n $NS exec $CP -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/status/runtimeinfo' 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']
print('  reloadConfigSuccess =',d.get('reloadConfigSuccess'))
print('  lastConfigTime      =',d.get('lastConfigTime'))"
echo "  (patch3 于 06:32 左右应用; lastConfigTime 应 >= 该时刻)"
