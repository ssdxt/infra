#!/bin/bash
P=http://127.0.0.1:9091
run() { curl -s --get "$P/api/v1/query" --data-urlencode "query=$1"; }
g() { run "$1" | python3 -c "
import sys,json
try:
  r=json.load(sys.stdin)['data']['result']
  print(r[0]['value'][1] if r else '0')
except Exception as e: print('ERR')"; }

echo "现在(UTC): $(date -u '+%H:%M:%S')   (第4条 drop 于 06:33:20 生效)"
echo
echo "===== [1] drop 是否生效(看这些序列最新时间戳是否已冻结) ====="
for m in ALERTS ALERTS_FOR_STATE count:up0 count:up1; do
  LAG=$(g "now() - max(timestamp($m{prometheus=~\"monitoring/.*\"}))")
  printf '  %-18s now-lag = %-10s 秒\n' "$m" "$LAG"
done
echo
echo "===== [2] 近 90 秒是否还有新的远程 ALERTS/count:up(应为 0) ====="
for m in ALERTS count:up1; do
  printf '  %-18s count_over_time[90s] = ' "$m"
  g "count(count_over_time($m{prometheus=~\"monitoring/.*\"}[90s]))"
done
echo
echo "===== [3] 对照: 正常指标仍在推进(now-lag 应 < 60) ====="
for m in apiserver_request_total node_cpu_seconds_total kube_node_info; do
  printf '  %-26s now-lag = %s 秒\n' "$m" "$(g "now() - max(timestamp($m{prometheus=~\"monitoring/.*\"}))")"
done
echo
echo "===== [4] container_memory_rss(唯一仍在报错的来源) ====="
printf '  远程序列数       = %s\n' "$(g "count(node_namespace_pod_container:container_memory_rss{prometheus=~\"monitoring/.*\"})")"
printf '  now-lag          = %s 秒\n' "$(g "now() - max(timestamp(node_namespace_pod_container:container_memory_rss{prometheus=~\"monitoring/.*\"}))")"
printf '  本地来源序列数   = %s  (=0 说明只有集群一份, 不存在双份覆盖)\n' "$(g "count(node_namespace_pod_container:container_memory_rss{prometheus!~\"monitoring/.*\"})")"
echo
echo "===== [5] 最近 20 分钟错误来源分布 ====="
docker logs wxq-prometheus --since 20m 2>&1 | grep 'Out of order sample' | grep -o '__name__=\\"[^"\\]*\\"' | sed 's/__name__=\\"//; s/\\"//' | sort | uniq -c | sort -rn
echo
echo "===== [6] 规则与告警健康 ====="
curl -s "$P/api/v1/rules" | python3 -c "
import sys,json
from collections import Counter
d=json.load(sys.stdin)['data']['groups']
c=Counter((r['type'],r.get('health')) for g in d for r in g['rules'])
print('  groups=%d rules=%d' % (len(d),sum(len(g['rules']) for g in d)))
for k,v in sorted(c.items()): print('    %-24s %s' % (str(k),v))
"
printf '  Alertmanager 告警数 = '
curl -s http://127.0.0.1:9093/api/v2/alerts | python3 -c "import sys,json;print(len(json.load(sys.stdin)))"
