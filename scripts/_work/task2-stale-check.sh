#!/bin/bash
P=http://10.100.10.29:9091
q() { curl -s --get "$P/api/v1/query" --data-urlencode "query=$1" | python3 -c "
import sys,json
try:
  r=json.load(sys.stdin)['data']['result']
  print(r[0]['value'][1] if r else '0')
except Exception as e: print('ERR',e)"; }

echo "===== 关键判据: 桶指标的最新时间戳 vs 现在 ====="
echo -n "  现在(now)                                          = "; q 'time()'
echo -n "  max(timestamp(apiserver_request_duration_seconds_bucket)) = "; q 'max(timestamp(apiserver_request_duration_seconds_bucket))'
echo -n "  max(timestamp({__name__=~\".*_bucket\"}))            = "; q 'max(timestamp({__name__=~\".*_bucket\"}))'
echo -n "  max(timestamp(kubernetes_feature_enabled))         = "; q 'max(timestamp(kubernetes_feature_enabled))'
echo "  --- 对照: 仍在正常推送的指标 ---"
echo -n "  max(timestamp(apiserver_request_total))            = "; q 'max(timestamp(apiserver_request_total))'
echo -n "  max(timestamp(node_cpu_seconds_total))             = "; q 'max(timestamp(node_cpu_seconds_total))'
echo
echo "  ^ 若 bucket 的时间戳 ≈ 补齐时间(06:15) 而 now 是 06:2x,"
echo "    说明这些是 patch 前的历史序列,已被 stale,不再有新样本 => drop 规则其实是生效的"
echo
echo "===== 只算最近 1 分钟仍有新样本的桶序列(真正的在推量) ====="
echo -n "  count(last_over_time 1m, 有值的桶指标名) = "
curl -s --get "$P/api/v1/query" --data-urlencode 'query=count(count by(__name__)({__name__=~".*_bucket"}[1m]))' | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print(r[0]['value'][1] if r else '0')"
echo -n "  count(last_over_time 1m 的 bucket 序列数) = "
curl -s --get "$P/api/v1/query" --data-urlencode 'query=count({__name__=~".*_bucket"}[1m])' | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print(r[0]['value'][1] if r else '0')"
echo
echo "===== 对照: 非 bucket 指标 1 分钟内有值的序列数 ====="
curl -s --get "$P/api/v1/query" --data-urlencode 'query=count({job="apiserver",__name__!~".*_bucket"}[1m])' | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print('  count({job=apiserver, 非bucket}[1m]) =', r[0]['value'][1] if r else '0')"
echo
echo "===== etcd job 为什么是 0 ====="
echo -n "  集群侧 etcd job 是否存在: 见后文集群检查"
curl -s --get "$P/api/v1/query" --data-urlencode 'query=count({job="etcd"})' >/dev/null
echo "  plant01 上 etcd_request_duration_seconds_bucket 序列数: $(q 'count(etcd_request_duration_seconds_bucket)')"
echo "  ^ etcd_* 指标其实是通过 apiserver 的 /metrics 暴露的(job=apiserver),不是独立 etcd job"
