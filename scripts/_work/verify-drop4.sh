#!/bin/bash
P=http://127.0.0.1:9091
run() { curl -s --get "$P/api/v1/query" --data-urlencode "query=$1"; }
g() { run "$1" | python3 -c "
import sys,json
try:
  r=json.load(sys.stdin)['data']['result']
  print(r[0]['value'][1] if r else '0')
except: print('ERR')"; }

echo "现在(UTC): $(date -u '+%H:%M:%S')"
echo
echo "===== [1] drop 规则(第4条)是否生效: 看这些序列【最新时间戳】 ====="
echo "  配置 06:33:20 生效, 现在应已明显滞后"
for m in 'ALERTS' 'ALERTS_FOR_STATE' 'count:up0' 'count:up1'; do
  printf '  %-18s max(timestamp) = %-22s ' "$m" "$(g "max(timestamp($m{prometheus=~\"monitoring/.*\"}))")"
  printf 'now-lag = %s 秒\n' "$(g "now() - max(timestamp($m{prometheus=~\"monitoring/.*\"}))")"
done
echo
echo "  --- 近 60 秒内是否还有新的远程 ALERTS/count:up 样本(应为 0) ---"
for m in 'ALERTS' 'count:up1'; do
  printf '  %-18s count_over_time[60s](远程来源) = ' "$m"
  g "count(count_over_time($m{prometheus=~\"monitoring/.*\"}[60s]))"
done
echo
echo "===== [2] 对照: 正常指标仍在推进 ====="
for m in 'apiserver_request_total' 'node_cpu_seconds_total'; do
  printf '  %-24s now-lag = %s 秒\n' "$m" "$(g "now() - max(timestamp($m{prometheus=~\"monitoring/.*\"}))")"
done
echo
echo "===== [3] (id 冲突源) node_namespace_pod_container:container_memory_rss 现状 ====="
printf '  远程序列数            = %s\n' "$(g "count(node_namespace_pod_container:container_memory_rss{prometheus=~\"monitoring/.*\"})")"
printf '  now-lag(仍在新写)     = %s 秒\n' "$(g "now() - max(timestamp(node_namespace_pod_container:container_memory_rss{prometheus=~\"monitoring/.*\"}))")"
printf '  本地来源序列数        = %s\n' "$(g "count(node_namespace_pod_container:container_memory_rss{prometheus!~\"monitoring/.*\"})")"
echo
echo "  --- 该指标在集群侧有多少序列? ---"
export KUBECONFIG=/etc/kubernetes/admin.conf
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- \
  wget -qO- 'http://localhost:9090/api/v1/query?query=count(node_namespace_pod_container:container_memory_rss)' 2>/dev/null | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print('    集群侧 =',r[0]['value'][1] if r else '0')"
echo
echo "===== [4] 错误来源统计(最近 20 分钟, 精确到 __name__) ====="
docker logs wxq-prometheus --since 20m 2>&1 | grep 'Out of order sample' | grep -o '__name__=\\"[^"\\]*\\"' | sed 's/__name__=\\"//; s/\\"//' | sort | uniq -c | sort -rn
echo
echo "  说明: 第4条 drop 规则只影响【新发送】的样本, 之前已入库的序列会保留到淘汰,"
echo "        所以短期内可能仍有零星残留错误。"
echo
echo "===== [5] 规则与告警仍健康 ====="
curl -s "$P/api/v1/rules" | python3 -c "
import sys,json
from collections import Counter
d=json.load(sys.stdin)['data']['groups']
c=Counter((r['type'],r.get('health')) for g in d for r in g['rules'])
print('  groups=%d rules=%d' % (len(d),sum(len(g['rules']) for g in d)), dict(c))
"
printf '  Alertmanager 告警数 = '
curl -s http://127.0.0.1:9093/api/v2/alerts | python3 -c "import sys,json;print(len(json.load(sys.stdin)))"
