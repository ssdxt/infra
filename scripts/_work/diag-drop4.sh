#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=monitoring; PROM=prometheus-stack-kube-prom-prometheus; CP=prometheus-$PROM-0
P=http://10.100.10.29:9091
run() { curl -s --get "$P/api/v1/query" --data-urlencode "query=$1"; }
g() { run "$1" | python3 -c "
import sys,json
try:
  r=json.load(sys.stdin)['data']['result']
  print(r[0]['value'][1] if r else '0')
except Exception as e: print('ERR:'+str(e)[:40])"; }

echo "===== [1] Prometheus 实际加载的配置里有没有第 4 条 ====="
echo -n "  config_out 中 remote_write 段含 ALERTS 的行数: "
kubectl -n $NS exec $CP -c prometheus -- sh -c \
  'sed -n "/^remote_write:/,/^[a-z_]*:/p" /etc/prometheus/config_out/prometheus.env.yaml | grep -c "ALERTS"' 2>&1
echo
echo "  完整 remote_write 段:"
kubectl -n $NS exec $CP -c prometheus -- sh -c \
  'sed -n "/^remote_write:/,/^[a-z_]*:/p" /etc/prometheus/config_out/prometheus.env.yaml' 2>&1
echo
echo "===== [2] reload 时间 ====="
kubectl -n $NS exec $CP -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/status/runtimeinfo' 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']
print('  reloadConfigSuccess =',d.get('reloadConfigSuccess'))
print('  lastConfigTime      =',d.get('lastConfigTime'))
print('  startTime           =',d.get('startTime'))"
echo
echo "===== [3] ALERTS / count:up1 最新样本时间 vs now ====="
echo "  (用两个独立查询, 避免复合表达式出错)"
for m in ALERTS count:up1; do
  TS=$(g "max(timestamp($m{prometheus=~\"monitoring/.*\"}))")
  echo "  $m  max(timestamp) = $TS"
done
echo -n "  现在 epoch = "
curl -s "$P/api/v1/query?query=time()" | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']
r=d.get('result')
if r: print(r[0]['value'][1])
else: print(d.get('value'))"
echo
echo "===== [4] 近 60 秒仍有样本? ====="
for m in ALERTS count:up1; do
  printf '  %-14s count_over_time[60s] = ' "$m"
  g "count(count_over_time($m{prometheus=~\"monitoring/.*\"}[60s]))"
done
echo
echo "===== [5] 渲染段里第4条正则是否被 operator 改写 ====="
kubectl -n $NS get prometheus $PROM -o jsonpath='{.spec.remoteWrite[0].writeRelabelConfigs[3]}' | python3 -m json.tool
