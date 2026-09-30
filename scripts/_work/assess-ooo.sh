#!/bin/bash
P=http://127.0.0.1:9091
echo "===== [1] 'Out of order' 错误的频率与影响面 ====="
echo "  最近 10 分钟错误条数:"
docker logs wxq-prometheus --since 10m 2>&1 | grep -c 'Out of order sample' || echo 0
echo "  涉及的不同 series(按 __name__ 归类):"
docker logs wxq-prometheus --since 10m 2>&1 | grep 'Out of order sample' | grep -o '__name__=\\"[^"\\]*\\"' | sort | uniq -c | sort -rn
echo
echo "  首次出现时间:"
docker logs wxq-prometheus --since 30m 2>&1 | grep 'Out of order sample' | head -1 | grep -o 'time=[^ ]*'
echo "  最后出现时间:"
docker logs wxq-prometheus --since 30m 2>&1 | grep 'Out of order sample' | tail -1 | grep -o 'time=[^ ]*'
echo
echo "===== [2] 除该错误外, 是否还有其他错误 ====="
docker logs wxq-prometheus --since 10m 2>&1 | grep -iE 'level=error|panic|fatal' | grep -v 'Out of order sample' | head -10 || true
echo "  (以上为空即只有 out-of-order 一种)"
echo
echo "===== [3] 影响评估: 集群数据是否仍在正常入库 ====="
for q in 'count(up{job="kubelet"})' 'count(kube_node_info)' 'count(apiserver_request_total)' 'count(node_cpu_seconds_total)' 'count(kube_pod_info)'; do
  printf '  %-42s = ' "$q"
  curl -s --get "$P/api/v1/query" --data-urlencode "query=$q" | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print(r[0]['value'][1] if r else '0')"
done
echo
echo "  集群 up 目标(近2分钟有数据):"
curl -s --get "$P/api/v1/query" --data-urlencode 'query=count(count by(instance)(last_over_time(up{job=~"kubelet|apiserver|node-exporter|kube-state-metrics"}[2m])))' | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print('   ',r[0]['value'][1] if r else '0')"
echo
echo "===== [4] 这两个冲突指标是什么(ALERTS / count:up*) ====="
echo "  plant01 自己的:"
curl -s --get "$P/api/v1/query" --data-urlencode 'query=count(count:up1)' | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print('    count(count:up1) =',r[0]['value'][1] if r else '0')"
curl -s --get "$P/api/v1/query" --data-urlencode 'query=count(ALERTS)' | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print('    count(ALERTS)    =',r[0]['value'][1] if r else '0')"
echo
echo "  集群推来的 ALERTS 样例标签:"
curl -s --get "$P/api/v1/query" --data-urlencode 'query=ALERTS{prometheus=~"monitoring/.*"}' | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print('    条数 =',len(r))
if r:
    m=r[0]['metric']
    for k in sorted(m): print('      %-34s = %s' % (k,m[k]))
"
echo
echo "===== [5] 判断: 是否为时间戳交错的良性噪声 ====="
echo "  · 若错误条数随时间不增长(每次 remote write 批次偶发) => 良性, 仅日志噪声"
echo "  · 采样两次比较:"
A=$(docker logs wxq-prometheus --since 2m 2>&1 | grep -c 'Out of order sample')
sleep 45
B=$(docker logs wxq-prometheus --since 2m 2>&1 | grep -c 'Out of order sample')
echo "    2 分钟窗口错误数: $A -> $B"
echo
echo "  remote write 队列(集群侧)健康度关键指标:"
export KUBECONFIG=/etc/kubernetes/admin.conf
for m in prometheus_remote_storage_samples_pending prometheus_remote_storage_failed_samples_total prometheus_remote_storage_shards prometheus_remote_storage_samples_total; do
  printf '    %-52s ' "$m"
  kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- "http://localhost:9090/api/v1/query?query=$m" 2>/dev/null | python3 -c "
import sys,json
try:
  r=json.load(sys.stdin)['data']['result']; print(r[0]['value'][1] if r else '0')
except: print('ERR')"
done
