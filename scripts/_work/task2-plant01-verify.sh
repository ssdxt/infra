#!/bin/bash
echo "===== [1] plant01 count(up) —— 基线是 9 ====="
curl -s 'http://10.100.10.29:9091/api/v1/query?query=count(up)' | python3 -c "import sys,json;print('  count(up) =',json.load(sys.stdin)['data']['result'][0]['value'][1])"
echo
echo "===== [2] 集群指标是否已到达(按 job 看) ====="
for j in kubelet node-exporter kube-state-metrics apiserver etcd coredns kube-scheduler kube-controller-manager prometheus-stack-kube-prom-prometheus prometheus-stack-kube-prom-alertmanager prometheus-stack-kube-prom-operator; do
  printf '  %-45s ' "$j"
  curl -s "http://10.100.10.29:9091/api/v1/query?query=count(%7Bjob%3D%22$j%22%7D)" | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print((r[0]['value'][1] if r else '0'))"
done
echo
echo "===== [3] 集群专属指标抽样(证明是集群推来的) ====="
for q in 'count(kube_node_info)' 'count(kube_pod_info)' 'count(node_uname_info)' 'count(apiserver_request_total)' 'count(kubelet_node_name)'; do
  printf '  %-38s ' "$q"
  curl -s "http://10.100.10.29:9091/api/v1/query?query=$q" | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print(r[0]['value'][1] if r else '0')"
done
echo
echo "===== [4] 外部标签是否带过来(cluster 来源标识) ====="
curl -s 'http://10.100.10.29:9091/api/v1/query?query=kube_node_info' | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print('  返回 %d 条' % len(r))
if r:
    m=r[0]['metric']
    print('  抽样标签:')
    for k,v in sorted(m.items()):
        if k not in ('__name__',): print('    %-42s = %s' % (k,v))
"
echo
echo "===== [5] plant01 侧 TSDB 规模(remote_write 后) ====="
curl -s 'http://10.100.10.29:9091/api/v1/status/tsdb' | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']['headStats']
print('  numSeries     =',d['numSeries'],' (基线 15523)')
print('  numLabelPairs =',d['numLabelPairs'],' (基线 2594)')
print('  chunkCount    =',d['chunkCount'],' (基线 74502)')
"
echo
echo "===== [6] plant01 磁盘/卷增长 ====="
df -h /data1 | tail -1
echo "  prometheus-data: $(du -sh /data1/docker/volumes/wxq-monitor_prometheus-data/_data 2>/dev/null | cut -f1)"
echo
echo "===== [7] 集群推来的数据是否也进了 VM(plant01 的长期存储) ====="
curl -s 'http://10.100.10.29:8428/api/v1/query?query=count(kube_node_info)' | head -c 300; echo
echo
echo "===== [8] 有无 remote write 被拒/报错的迹象 ====="
docker logs wxq-prometheus --tail 100 2>&1 | grep -iE 'remote|error|400|refus|invalid' | tail -10 || echo "  (无相关日志)"
