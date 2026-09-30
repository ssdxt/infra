#!/bin/bash
P=http://127.0.0.1:9091
echo "现在(UTC): $(date -u '+%H:%M:%S')"
echo
echo "===== [1] out-of-order 错误: 按时间分段统计 ====="
echo "  全部(近 60 分钟)总条数:"
docker logs wxq-prometheus --since 60m 2>&1 | grep -c 'Out of order sample'
echo
echo "  按分钟统计(时间戳 -> 条数):"
docker logs wxq-prometheus --since 60m 2>&1 | grep 'Out of order sample' \
  | grep -o 'time=2026-[0-9T:]*' | cut -c1-19 | sort | uniq -c | tail -20
echo
echo "===== [2] 06:34 之后是否还有(配置 06:33:20 生效) ====="
AFTER=$(docker logs wxq-prometheus --since 60m 2>&1 | grep 'Out of order sample' | grep -cE 'time=2026-09-29T06:3[4-9]|time=2026-09-29T06:[4-9]')
echo "  06:34 以后条数 = $AFTER"
echo
echo "===== [3] 等待 90 秒后再看增量(应从 0 开始) ====="
A=$(docker logs wxq-prometheus --since 90s 2>&1 | grep -c 'Out of order sample')
echo "  近 90 秒 = $A"
sleep 90
B=$(docker logs wxq-prometheus --since 90s 2>&1 | grep -c 'Out of order sample')
echo "  再过 90 秒 = $B"
echo
echo "  ^ 两者都为 0 => 噪声已消除"
echo
echo "===== [4] 数据仍在正常入库(不受过滤影响) ====="
for q in 'count(up{job="kubelet"})' 'count(kube_node_info)' 'count(kube_pod_info)' 'count(apiserver_request_total)' 'count(node_cpu_seconds_total)' 'count(kubelet_node_name)'; do
  printf '  %-40s = ' "$q"
  curl -s --get "$P/api/v1/query" --data-urlencode "query=$q" | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print(r[0]['value'][1] if r else '0')"
done
echo
echo "===== [5] 被丢弃的序列确认已不再新增 ====="
for m in ALERTS count:up1; do
  printf '  %-16s 集群推来的(带 prometheus 标签) = ' "$m"
  curl -s --get "$P/api/v1/query" --data-urlencode "query=count(last_over_time($m{prometheus=~\"monitoring/.*\"}[2m]))" | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print(r[0]['value'][1] if r else '0')"
done
echo "  --- 对照: plant01 自己算的仍在 ---"
printf '  %-16s plant01 本地 = ' "ALERTS"
curl -s --get "$P/api/v1/query" --data-urlencode 'query=count(last_over_time(ALERTS{prometheus!~"monitoring/.*"}[2m]))' | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print(r[0]['value'][1] if r else '0')"
echo
echo "===== [6] 规则健康度仍全 ok ====="
curl -s "$P/api/v1/rules" | python3 -c "
import sys,json
from collections import Counter
d=json.load(sys.stdin)['data']['groups']
c=Counter((r['type'],r.get('health')) for g in d for r in g['rules'])
print('  groups=%d rules=%d' % (len(d),sum(len(g['rules']) for g in d)))
for k,v in sorted(c.items()): print('    %-24s %s' % (str(k),v))
"
echo
echo "===== [7] 告警链路仍在工作 ====="
curl -s 'http://127.0.0.1:9093/api/v2/alerts' | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('  Alertmanager 当前告警 = %d 条' % len(d))
"
