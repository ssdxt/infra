#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
P=prometheus-prometheus-stack-kube-prom-prometheus-0
NS=monitoring
echo "===== [1] config-reloader 是否已热加载 ====="
kubectl -n $NS logs $P -c config-reloader --tail 15 2>&1
echo
echo "===== [2] Prometheus 自身 reload 状态 ====="
kubectl -n $NS exec $P -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/status/runtimeinfo' 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']
print('  reloadConfigSuccess =', d.get('reloadConfigSuccess'))
print('  lastConfigTime      =', d.get('lastConfigTime'))
print('  startTime           =', d.get('startTime'))
"
echo
echo "===== [3] 集群侧 remote write 队列指标 ====="
for m in prometheus_remote_storage_samples_total \
         prometheus_remote_storage_succeeded_samples_total \
         prometheus_remote_storage_failed_samples_total \
         prometheus_remote_storage_samples_pending \
         prometheus_remote_storage_samples_dropped_total \
         prometheus_remote_storage_shards \
         prometheus_remote_storage_queue_highest_sent_timestamp_seconds \
         prometheus_remote_storage_highest_timestamp_in_seconds; do
  printf '  %-56s ' "$m"
  kubectl -n $NS exec $P -c prometheus -- wget -qO- "http://localhost:9090/api/v1/query?query=$m" 2>/dev/null | python3 -c "
import sys,json
try:
  r=json.load(sys.stdin)['data']['result']
  print(' | '.join('%s=%s'%(x['metric'].get('url','-')[:46], x['value'][1]) for x in r) if r else '(无数据)')
except Exception as e: print('ERR',e)"
done
echo
echo "===== [4] 等 30s 再采样, 看是否有样本成功送达 ====="
get() { kubectl -n $NS exec $P -c prometheus -- wget -qO- "http://localhost:9090/api/v1/query?query=$1" 2>/dev/null | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print(r[0]['value'][1] if r else 'NA')"; }
A=$(get prometheus_remote_storage_samples_total)
B=$(get prometheus_remote_storage_samples_failed_total)
sleep 30
A2=$(get prometheus_remote_storage_samples_total)
B2=$(get prometheus_remote_storage_samples_failed_total)
echo "  samples_total : $A -> $A2   (+$(( ${A2%.*} - ${A%.*} )))"
echo "  failed_total  : $B -> $B2"
echo
echo "===== [5] 最近日志中的 remote write 错误 ====="
kubectl -n $NS logs $P -c prometheus --tail 300 2>&1 | grep -iE 'remote|error|refused|timeout' | tail -15 || echo "  (无 remote/error 相关日志)"
echo
echo "===== [6] Pod 状态 ====="
kubectl -n $NS get pods -l app.kubernetes.io/name=prometheus -o wide
