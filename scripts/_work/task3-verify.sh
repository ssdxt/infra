#!/bin/bash
P=http://127.0.0.1:9091
echo "===== [1] /api/v1/rules 返回的 group 结构(看有无 file 字段) ====="
curl -s "$P/api/v1/rules" | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']['groups']
print('  group 总数 =',len(d))
print('  第一个 group 的所有 key:', sorted(d[0].keys()))
print()
print('  前 20 个 group: name / file / interval / 规则数')
for g in d[:20]:
    print('    %-42s file=%-46s rules=%d' % (g.get('name'), g.get('file','<无file字段>'), len(g['rules'])))
"
echo
echo "===== [2] 直接查集群规则名是否加载 ====="
curl -s "$P/api/v1/rules" | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']['groups']
names={r['name'] for g in d for r in g['rules']}
total=sum(len(g['rules']) for g in d)
print('  规则总数(本次加载) =',total)
print('  唯一规则名 =',len(names))
print()
for n in ['KubeNodeNotReady','KubeAPIErrorBudgetBurn','KubeletClientCertificateExpiration','NodeFilesystemSpaceFillingUp','KubePodCrashLooping','AlertmanagerFailedReload']:
    print('    %-42s %s' % (n, '✅ 已加载' if n in names else '❌ 未加载'))
print()
print('  集群特有规则抽样(应属 230 条内的):')
cluster=[n for n in sorted(names) if n.startswith(('Kube','Node','Alertmanager','CPU','etcd','Info','Config','Target','Prometheus','Namespace','PersistentVolume'))]
for n in cluster[:25]: print('    ',n)
"
echo
echo "===== [3] 规则健康度(区分 alerting/recording) ====="
curl -s "$P/api/v1/rules" | python3 -c "
import sys,json
from collections import Counter
d=json.load(sys.stdin)['data']['groups']
c=Counter(); bytype=Counter()
for g in d:
    for r in g['rules']:
        c[(r['type'],r.get('health'))]+=1
        bytype[r['type']]+=1
print('  按类型:',dict(bytype))
print('  按(类型,健康):')
for k,v in sorted(c.items()): print('    %-22s %s' % (str(k),v))
bad=[(r['name'],g['name'],r.get('health'),(r.get('lastError') or '')[:100]) for g in d for r in g['rules'] if r.get('health')!='ok']
print()
if bad:
    print('  ⚠️ 非 ok 规则 %d 条:' % len(bad))
    for n,g,h,e in bad[:30]: print('     %-48s group=%-38s health=%-8s %s' % (n,g,h,e))
else:
    print('  ✅ 全部规则 health=ok')
"
echo
echo "===== [4] 重复记录规则(来自集群上游规则的固有重复) ====="
curl -s "$P/api/v1/rules" | python3 -c "
import sys,json
from collections import defaultdict
d=json.load(sys.stdin)['data']['groups']
m=defaultdict(list)
for g in d:
    for r in g['rules']:
        if r['type']=='recording': m[r['name']].append((g['name'], tuple(sorted((l['name'],l['value']) for l in r.get('labels',[])))))
dups={k:v for k,v in m.items() if len(v)>1}
print('  同名+同标签的 recording 规则(会互相覆盖) %d 个:' % len(dups))
for k,v in sorted(dups.items()):
    print('    %-52s x%d  groups=%s' % (k,len(v),[x[0] for x in v]))
"
echo
echo "===== [5] 集群侧同一规则的情况(证明是上游固有, 非本次引入) ====="
export KUBECONFIG=/etc/kubernetes/admin.conf
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- \
  wget -qO- 'http://localhost:9090/api/v1/rules?type=record' 2>/dev/null | python3 -c "
import sys,json
from collections import Counter
d=json.load(sys.stdin)['data']['groups']
c=Counter(r['name'] for g in d for r in g['rules'])
print('  集群侧 recording 规则: 总数=%d 唯一名=%d' % (sum(c.values()),len(c)))
print('  集群侧同名多次的规则:')
for k,v in sorted(c.items()):
    if v>1: print('    %-52s x%d' % (k,v))
"
