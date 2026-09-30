#!/bin/bash
P=http://10.100.10.29:9091
echo "===== plant01 TSDB 规模(过滤生效后) ====="
curl -s "$P/api/v1/status/tsdb" | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']
print('  numSeries     =',d['headStats']['numSeries'],' (本地基线 15523)')
print('  numLabelPairs =',d['headStats']['numLabelPairs'])
print()
print('  Top10 指标名:')
for x in d['seriesCountByMetricName'][:10]:
    print('    %-58s %s' % (x['name'],x['value']))
"
echo
echo "===== 实际仍在推送的 job 规模(活跃量, 排除历史残留) ====="
for j in kubelet node-exporter kube-state-metrics apiserver coredns kube-scheduler kube-controller-manager prometheus-stack-kube-prom-prometheus prometheus-stack-kube-prom-alertmanager prometheus-stack-kube-prom-operator; do
  printf '  %-45s ' "$j"
  curl -s --get "$P/api/v1/query" --data-urlencode "query=count(last_over_time(up{job=\"$j\"}[2m]))" | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print(r[0]['value'][1] if r else '0')"
done
echo
echo "===== 活跃序列数(近 2 分钟仍有新样本的集群序列) ====="
for j in apiserver kubelet node-exporter kube-state-metrics; do
  printf '  job=%-22s 活跃序列 = ' "$j"
  curl -s --get "$P/api/v1/query" --data-urlencode "query=count(last_over_time({job=\"$j\"}[2m]))" | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print(r[0]['value'][1] if r else '0')"
done
echo
echo "===== count(up) / 集群指标可用性 ====="
for q in 'count(up)' 'count(kube_node_info)' 'count(kube_pod_info)' 'count(apiserver_request_total)' 'count(node_cpu_seconds_total)' 'count(kubelet_node_name)' 'count(up{job="apiserver"})'; do
  printf '  %-38s = ' "$q"
  curl -s --get "$P/api/v1/query" --data-urlencode "query=$q" | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print(r[0]['value'][1] if r else '0')"
done
echo
echo "===== 磁盘 ====="
df -h /data1 | tail -1
echo "  prometheus-data 卷: $(du -sh /data1/docker/volumes/wxq-monitor_prometheus-data/_data 2>/dev/null | cut -f1)"
