#!/bin/bash
P=http://10.100.10.29:9091
run() { curl -s --get "$P/api/v1/query" --data-urlencode "query=$1"; }
one() { run "$1" | python3 -c "
import sys,json
try:
  r=json.load(sys.stdin)['data']['result']
  print(r[0]['value'][1] if r else 'NA')
except: print('NA')"; }

echo "现在: $(date -u '+%H:%M:%S UTC')"
echo
echo "===== 逐窗口统计 bucket 样本数(在 plant01 上) ====="
for w in 30s 1m 2m 5m 10m; do
  printf '  count_over_time(bucket apiserver [%-4s]) 序列数 = %-8s ' "$w" "$(one "count(count_over_time({__name__=~\".*_bucket\",job=\"apiserver\"}[$w]))")"
  printf '| 样本总数 = %s\n' "$(one "sum(count_over_time({__name__=~\".*_bucket\",job=\"apiserver\"}[$w]))")"
done
echo
echo "===== 对照: 非 bucket 的 apiserver 指标 ====="
for w in 1m 5m; do
  printf '  count_over_time(apiserver 非bucket [%-4s]) 序列数 = %s\n' "$w" "$(one "count(count_over_time({job=\"apiserver\",__name__!~\".*_bucket\"}[$w]))")"
done
echo
echo "===== 每 20 秒连续观察 3 次: bucket 是否还有任何新样本 ====="
for i in 1 2 3; do
  printf '  [%s] bucket[20s] 序列=%s 样本=%s | total[20s] 序列=%s\n' \
    "$(date -u '+%H:%M:%S')" \
    "$(one "count(count_over_time({__name__=~\".*_bucket\",job=\"apiserver\"}[20s]))")" \
    "$(one "sum(count_over_time({__name__=~\".*_bucket\",job=\"apiserver\"}[20s]))")" \
    "$(one "count(count_over_time(apiserver_request_total[20s]))")"
  [ $i -lt 3 ] && sleep 20
done
echo
echo "===== 集群侧: remote write 发送速率(过滤后应显著低于过滤前) ====="
export KUBECONFIG=/etc/kubernetes/admin.conf
A=$(kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/query?query=prometheus_remote_storage_samples_total' 2>/dev/null | python3 -c "
import sys,json;r=json.load(sys.stdin)['data']['result'];print(r[0]['value'][1] if r else 'NA')")
sleep 30
B=$(kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/query?query=prometheus_remote_storage_samples_total' 2>/dev/null | python3 -c "
import sys,json;r=json.load(sys.stdin)['data']['result'];print(r[0]['value'][1] if r else 'NA')")
echo "  samples_total: $A -> $B"
python3 -c "
try:
    print('  发送速率 = %.0f samples/s  (30s 窗口)' % (($B-$A)/30))
except: print('  无法计算')"
echo
echo "  队列健康:"
for m in prometheus_remote_storage_samples_pending prometheus_remote_storage_failed_samples_total prometheus_remote_storage_shards; do
  printf '    %-50s %s\n' "$m" "$(kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- "http://localhost:9090/api/v1/query?query=$m" 2>/dev/null | python3 -c "
import sys,json
try:
  r=json.load(sys.stdin)['data']['result'];print(r[0]['value'][1] if r else '0')
except: print('ERR')")"
done
