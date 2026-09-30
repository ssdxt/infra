#!/bin/bash
P=http://10.100.10.29:9091
run() { curl -s --get "$P/api/v1/query" --data-urlencode "query=$1"; }
g() { run "$1" | python3 -c "
import sys,json
try:
  r=json.load(sys.stdin)['data']['result']
  print(r[0]['value'][1] if r else 'NA')
except Exception as e: print('NA')"; }

echo "===== 现在 ====="
date -u '+  %H:%M:%S UTC'
echo
echo "===== 核心判据: bucket 最新样本时间戳 是否还在推进 ====="
echo "  (配置在 $(date -u -d '3 minutes ago' '+%H:%M' ) 左右被改为 .*_bucket)"
echo
for i in 1 2 3 4; do
  printf '  第%d次 (%s):\n' "$i" "$(date -u '+%H:%M:%S')"
  printf '    bucket   max(timestamp) = %s\n' "$(g 'max(timestamp({__name__=~".*_bucket",job="apiserver"}))')"
  printf '    total    max(timestamp) = %s\n' "$(g 'max(timestamp(apiserver_request_total))')"
  printf '    nodecpu  max(timestamp) = %s\n' "$(g 'max(timestamp(node_cpu_seconds_total))')"
  [ $i -lt 4 ] && sleep 25
done
echo
echo "===== 近 60 秒内是否还有新的 bucket 样本 ====="
printf '  count_over_time(bucket[60s]) 序列数 = '
run 'count_over_time({__name__=~".*_bucket",job="apiserver"}[60s])' | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print(len(r) if r else 0)"
printf '  对照 count_over_time(total[60s]) 序列数 = '
run 'count_over_time(apiserver_request_total[60s])' | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print(len(r) if r else 0)"
echo
echo "  解读: bucket 时间戳冻结 + 近60秒序列数远小于 9 万 => drop 已生效"
echo "        bucket 时间戳继续推进              => drop 仍未生效"
echo
echo "===== 集群侧 remote write 队列是否健康(用量下降说明过滤生效) ====="
export KUBECONFIG=/etc/kubernetes/admin.conf
for m in prometheus_remote_storage_samples_total prometheus_remote_storage_samples_pending prometheus_remote_storage_bytes_total; do
  printf '  %-48s ' "$m"
  kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- \
    wget -qO- "http://localhost:9090/api/v1/query?query=$m" 2>/dev/null | python3 -c "
import sys,json
try:
  r=json.load(sys.stdin)['data']['result']
  print(' | '.join(x['value'][1] for x in r) if r else '(无数据)')
except: print('ERR')"
done
