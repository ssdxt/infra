#!/bin/bash
P=http://10.100.10.29:9091
q() { curl -s --get "$P/api/v1/query" --data-urlencode "query=$1" | python3 -c "
import sys,json
try:
  r=json.load(sys.stdin)['data']['result']
  print(r[0]['value'][1] if r else '0 (无数据)')
except Exception as e: print('ERR',e)"; }

echo "===== [1] drop 规则是否生效:直接查被丢弃的指标 ====="
echo -n "  count(apiserver_request_duration_seconds_bucket) = "; q 'count(apiserver_request_duration_seconds_bucket)'
echo -n "  count({__name__=~\".*_bucket\"})                   = "; q 'count({__name__=~".*_bucket"})'
echo -n "  count(kubernetes_feature_enabled)                 = "; q 'count(kubernetes_feature_enabled)'
echo -n "  count(node_cpu_seconds_total)                     = "; q 'count(node_cpu_seconds_total)'
echo
echo "  ^ 若前两项为 0/无数据 => drop 生效; 若很大 => drop 未生效"
echo
echo "===== [2] 集群侧对照(未过滤时应有的数量) ====="
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "  (集群侧数值见前文: apiserver 113172 序列)"
echo
echo "===== [3] apiserver 到底推来了哪些指标(看看 113410 的构成) ====="
curl -s --get "$P/api/v1/label/__name__/values" --data-urlencode 'match[]={job="apiserver"}' | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']
print('  job=apiserver 下不同指标名 %d 个:' % len(d))
b=[x for x in d if x.endswith('_bucket')]
nb=[x for x in d if not x.endswith('_bucket')]
print('    其中 _bucket 类: %d 个' % len(b))
print('    其中 非bucket  : %d 个' % len(nb))
print()
print('  非 bucket 指标(最多 30 个):')
for x in nb[:30]: print('    ', x)
"
echo
echo "===== [4] plant01 TSDB 序列数再测(等待 stale 清理后) ====="
curl -s "$P/api/v1/status/tsdb" | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']
print('  numSeries =',d['headStats']['numSeries'])
print()
print('  Top8 指标名:')
for x in d['seriesCountByMetricName'][:8]:
    print('    %-55s %s' % (x['name'],x['value']))
"
