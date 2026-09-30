#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== plant01 上 apiserver bucket 样本的完整标签集(确认来源) ====="
curl -s --get 'http://10.100.10.29:9091/api/v1/query' \
  --data-urlencode 'query=apiserver_request_duration_seconds_bucket' | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print('  返回 %d 条' % len(r))
if r:
    m=r[0]['metric']
    for k,v in sorted(m.items()):
        print('    %-40s = %s' % (k,v))
"
echo
echo "===== 对照: 集群侧同一序列的标签(应基本一致) ====="
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- \
  wget -qO- 'http://localhost:9090/api/v1/query?query=apiserver_request_duration_seconds_bucket' 2>/dev/null | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print('  返回 %d 条' % len(r))
if r:
    m=r[0]['metric']
    for k,v in sorted(m.items()):
        print('    %-40s = %s' % (k,v))
"
echo
echo "===== 关键判据: bucket 是否带 monitor=\"wxq-monitor\"(plant01 本地) 还是 prometheus=\"monitoring/...\"(集群) ====="
curl -s --get 'http://10.100.10.29:9091/api/v1/series' \
  --data-urlencode 'match[]=apiserver_request_duration_seconds_bucket' \
  --data-urlencode 'start=1790660000' --data-urlencode 'end=1790663000' | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']
print('  序列数 =',len(d))
keys=set()
for s in d: keys.update(s.keys())
print('  出现过的标签名:', sorted(keys))
print()
print('  prometheus 标签取值集合:', sorted({s.get('prometheus','<无>') for s in d})[:5])
print('  job 标签取值集合       :', sorted({s.get('job','<无>') for s in d})[:5])
print('  monitor 标签取值集合   :', sorted({s.get('monitor','<无>') for s in d})[:5])
"
