#!/bin/bash
P=http://10.100.10.29:9091
run() { curl -s --get "$P/api/v1/query" --data-urlencode "query=$1"; }
g() { run "$1" | python3 -c "
import sys,json
try:
  r=json.load(sys.stdin)['data']['result']
  print(r[0]['value'][1] if r else '0')
except: print('0')"; }

echo "=========== plant01 稳定性观察窗口 (每 30s 采样, 共 5 次) ==========="
for i in $(seq 1 5); do
  OOO=$(docker logs wxq-prometheus --since 60s 2>&1 | grep -c 'Out of order sample')
  NUP=$(g 'count(count(up{prometheus=~"monitoring/.*"}))')
  printf '  [%s] 近60s out-of-order=%-3s count(up 集群来源)=%-4s 进程状态=%s\n' \
    "$(date -u '+%H:%M:%S')" "$OOO" "$NUP" \
    "$(docker inspect wxq-prometheus --format '{{.State.Status}}')"
  [ $i -lt 5 ] && sleep 30
done

echo
echo "=========== 最终交付状态 ==========="
echo "--- 1) remote_write 接收端(任务1) ---"
printf '  /api/v1/status/runtimeinfo HTTP %s | POST /api/v1/write HTTP %s (400=接收端已开)\n' \
  "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:9091/api/v1/status/runtimeinfo)" \
  "$(curl -s -o /dev/null -w '%{http_code}' -XPOST http://127.0.0.1:9091/api/v1/write)"
docker inspect wxq-prometheus --format '  启动参数含接收端: {{range .Args}}{{if eq . "--web.enable-remote-write-receiver"}}YES{{end}}{{end}}'
echo
echo "--- 2) 集群数据到达(任务2) ---"
printf '  count(up 全部)          = %s   (基线 9)\n' "$(g 'count(up)')"
printf '  count(up 集群来源)      = %s\n' "$(g 'count(count(up{prometheus=~\"monitoring/.*\"}))')"
printf '  kube_node_info          = %s   (11 节点)\n' "$(g 'count(kube_node_info)')"
printf '  kube_pod_info           = %s\n' "$(g 'count(kube_pod_info)')"
printf '  apiserver_request_total = %s\n' "$(g 'count(apiserver_request_total)')"
printf '  etcd_request_duration_seconds_count = %s (etcd 指标经 apiserver 暴露)\n' "$(g 'count(etcd_request_duration_seconds_count)')"
echo
echo "--- 3) 规则同步(任务3) ---"
curl -s "$P/api/v1/rules" | python3 -c "
import sys,json
from collections import Counter
d=json.load(sys.stdin)['data']['groups']
c=Counter()
for g in d:
    for r in g['rules']: c[(r['type'],r.get('health'))]+=1
print('  groups=%d  rules=%d' % (len(d),sum(len(g['rules']) for g in d)))
for k,v in sorted(c.items()): print('    %-26s %s' % (str(k),v))
new=[g for g in d if g.get('file','').endswith('cluster-wxq-rules.yaml')]
na=sum(1 for g in new for r in g['rules'] if r['type']=='alerting')
nr=sum(1 for g in new for r in g['rules'] if r['type']=='recording')
print('  集群规则文件: %d 组, alerting=%d recording=%d 合计=%d' % (len(new),na,nr,na+nr))
names={r['name'] for g in new for r in g['rules']}
print('  集群规则唯一名 =',len(names))
"
echo
echo "--- 4) 告警链 ---"
printf '  Alertmanager 当前告警 = %s 条\n' "$(curl -s http://127.0.0.1:9093/api/v2/alerts | python3 -c 'import sys,json;print(len(json.load(sys.stdin)))')"
echo "  集群来源的告警(instance_name 为空/带 prometheus 标签的)抽样:"
curl -s http://127.0.0.1:9093/api/v2/alerts | python3 -c "
import sys,json
d=json.load(sys.stdin)
seen={}
for a in d:
    n=a['labels'].get('alertname')
    seen[n]=seen.get(n,0)+1
for n,c in sorted(seen.items()): print('    %-40s x%d' % (n,c))
"
echo
echo "--- 5) 规模/磁盘 ---"
curl -s "$P/api/v1/status/tsdb" | python3 -c "
import sys,json
h=json.load(sys.stdin)['data']['headStats']
print('  plant01 numSeries =',h['numSeries'],' (本地基线 15523)')
"
df -h /data1 | tail -1 | sed 's/^/  /'
echo "  prometheus-data 卷: $(du -sh /data1/docker/volumes/wxq-monitor_prometheus-data/_data 2>/dev/null | cut -f1)"
echo
echo "--- 6) 其余容器状态 ---"
docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -i wxq
