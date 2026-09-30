#!/bin/bash
echo "===== plant01 Prometheus 规模(remote_write 前基线) ====="
curl -s 'http://10.100.10.29:9091/api/v1/status/tsdb' | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']
h=d['headStats']
print('  numSeries     =',h['numSeries'])
print('  numLabelPairs =',h['numLabelPairs'])
print('  chunkCount    =',h['chunkCount'])
print()
print('  Top10 指标名:')
for x in d['seriesCountByMetricName'][:10]:
    print('    %-55s %s' % (x['name'],x['value']))
"
echo
echo "===== 数据卷剩余空间 ====="
df -h /data1 | tail -1
echo "  prometheus-data 卷当前大小: $(du -sh /data1/docker/volumes/wxq-monitor_prometheus-data/_data 2>/dev/null | cut -f1)"
echo "  VM 数据卷当前大小: $(du -sh /data1/docker/volumes/wxq-monitor_vm-data/_data 2>/dev/null | cut -f1)"
echo
echo "===== count(up) 基线 ====="
curl -s 'http://10.100.10.29:9091/api/v1/query?query=count(up)' | python3 -c "import sys,json;print('  count(up) =',json.load(sys.stdin)['data']['result'][0]['value'][1])"
echo "===== 集群指标是否已存在(基线:应为空) ====="
curl -s 'http://10.100.10.29:9091/api/v1/query?query=count(%7Bjob%3D%22kubelet%22%7D)' | python3 -c "import sys,json;r=json.load(sys.stdin)['data']['result'];print('  count({job=\"kubelet\"}) =',r[0]['value'][1] if r else '0 (无集群数据, 符合预期)')"
