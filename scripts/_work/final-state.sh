#!/bin/bash
# 在 control-01 上运行: HTTP 查 plant01(10.100.10.29:9091), kubectl 查本集群
P=http://10.100.10.29:9091
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=monitoring; CP=prometheus-prometheus-stack-kube-prom-prometheus-0
run() { curl -s --get "$P/api/v1/query" --data-urlencode "query=$1"; }
g() { run "$1" | python3 -c "
import sys,json
try:
  r=json.load(sys.stdin)['data']['result']
  print(r[0]['value'][1] if r else '0')
except Exception as e: print('ERR')"; }

echo "现在(UTC): $(date -u '+%H:%M:%S')   (第4条 drop 于 06:33:20 生效)"
echo
echo "===== [1] drop 是否生效: 被丢弃序列的最新时间戳是否已冻结 ====="
for m in ALERTS ALERTS_FOR_STATE count:up0 count:up1; do
  printf '  %-18s now-lag = %-12s 秒\n' "$m" "$(g "now() - max(timestamp($m{prometheus=~\"monitoring/.*\"}))")"
done
echo
echo "===== [2] 近 90 秒是否还有新样本(应为 0) ====="
for m in ALERTS count:up1; do
  printf '  %-18s count_over_time[90s] = ' "$m"
  g "count(count_over_time($m{prometheus=~\"monitoring/.*\"}[90s]))"
done
echo
echo "===== [3] 对照: 正常集群指标仍在推进(now-lag 应 < 60 秒) ====="
for m in apiserver_request_total node_cpu_seconds_total kube_node_info kube_pod_info; do
  printf '  %-28s now-lag = %s 秒\n' "$m" "$(g "now() - max(timestamp($m{prometheus=~\"monitoring/.*\"}))")"
done
echo
echo "===== [4] 残留报错来源 container_memory_rss ====="
printf '  远程(集群推来)序列数 = %s\n' "$(g "count(node_namespace_pod_container:container_memory_rss{prometheus=~\"monitoring/.*\"})")"
printf '  本地序列数           = %s\n' "$(g "count(node_namespace_pod_container:container_memory_rss{prometheus!~\"monitoring/.*\"})")"
printf '  now-lag              = %s 秒\n' "$(g "now() - max(timestamp(node_namespace_pod_container:container_memory_rss{prometheus=~\"monitoring/.*\"}))")"
echo
echo "===== [5] 集群侧 remote write 队列健康 ====="
for m in prometheus_remote_storage_samples_total prometheus_remote_storage_samples_pending prometheus_remote_storage_shards; do
  printf '  %-48s ' "$m"
  kubectl -n $NS exec $CP -c prometheus -- wget -qO- "http://localhost:9090/api/v1/query?query=$m" 2>/dev/null | python3 -c "
import sys,json
try:
  r=json.load(sys.stdin)['data']['result']; print(r[0]['value'][1] if r else '0')
except: print('ERR')"
done
echo
echo "===== [6] plant01 规则健康 ====="
curl -s "$P/api/v1/rules" | python3 -c "
import sys,json
from collections import Counter
d=json.load(sys.stdin)['data']['groups']
c=Counter((r['type'],r.get('health')) for g in d for r in g['rules'])
print('  groups=%d rules=%d' % (len(d),sum(len(g['rules']) for g in d)))
for k,v in sorted(c.items()): print('    %-24s %s' % (str(k),v))
"
echo
echo "===== [7] plant01 数据规模/磁盘 ====="
curl -s "$P/api/v1/status/tsdb" | python3 -c "
import sys,json
h=json.load(sys.stdin)['data']['headStats']
print('  numSeries =',h['numSeries'],'  (本地基线 15523)')
"
printf '  count(up) = '; g 'count(up)'
