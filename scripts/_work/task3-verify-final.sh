#!/bin/bash
P=http://127.0.0.1:9091
echo "===== [1] 规则加载总览 ====="
curl -s "$P/api/v1/rules" | python3 -c "
import sys,json
from collections import Counter
d=json.load(sys.stdin)['data']['groups']
tot=sum(len(g['rules']) for g in d)
print('  groups = %d   rules = %d' % (len(d),tot))
print()
c=Counter(); 
for g in d:
    for r in g['rules']:
        c[(r['type'],r.get('health'))]+=1
print('  按(类型,健康):')
for k,v in sorted(c.items()): print('    %-24s %s' % (str(k),v))
print()
new=[g for g in d if g.get('file','').endswith('cluster-wxq-rules.yaml')]
print('  cluster-wxq-rules.yaml: %d 个组, %d 条规则' % (len(new), sum(len(g['rules']) for g in new)))
na=sum(1 for g in new for r in g['rules'] if r['type']=='alerting')
nr=sum(1 for g in new for r in g['rules'] if r['type']=='recording')
print('    alerting=%d  recording=%d' % (na,nr))
print()
print('  涉及文件:')
for f in sorted({g.get('file') for g in d}): print('   ',f)
"
echo
echo "===== [2] 非 ok 规则明细(应为空) ====="
curl -s "$P/api/v1/rules" | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']['groups']
bad=[(r['name'],g['name'],r.get('health'),(r.get('lastError') or '')[:110]) for g in d for r in g['rules'] if r.get('health')!='ok']
if bad:
    print('  ⚠️ %d 条:' % len(bad))
    for n,g,h,e in bad: print('     %-44s group=%-42s %-8s %s' % (n,g,h,e))
else:
    print('  ✅ 全部 279 条规则 health=ok(无加载错误)')
"
echo
echo "===== [3] 抽样确认集群规则已加载 ====="
curl -s "$P/api/v1/rules" | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']['groups']
names={r['name'] for g in d for r in g['rules']}
tests=['KubeNodeNotReady','KubeAPIErrorBudgetBurn','KubeletClientCertificateExpiration',
       'NodeFilesystemSpaceFillingUp','KubePodCrashLooping','AlertmanagerFailedReload',
       'KubeDeploymentReplicasMismatch','CPUThrottlingHigh','KubeletTooManyPods',
       'NodeFilesystemAlmostOutOfSpace','KubePersistentVolumeFillingUp','InfoInhibitor']
for n in tests: print('    %-44s %s' % (n,'✅' if n in names else '❌'))
print()
print('  规则名总数 =',len(names))
recs=[n for n in names if ':' in n]
print('  recording 规则名(含冒号) =',len(recs))
for n in sorted(recs)[:8]: print('    ',n)
"
echo
echo "===== [4] 上游固有的重复 lint(定位到具体规则) ====="
docker exec wxq-prometheus promtool check rules /etc/prometheus/rules/cluster-wxq-rules.yaml 2>&1 | tail -12
echo
echo "===== [5] 集群侧对照:该重复在集群上也存在 ====="
export KUBECONFIG=/etc/kubernetes/admin.conf
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- \
  wget -qO- 'http://localhost:9090/api/v1/rules?type=record' 2>/dev/null | python3 -c "
import sys,json
from collections import Counter
d=json.load(sys.stdin)['data']['groups']
c=Counter(r['name'] for g in d for r in g['rules'])
print('  集群侧 recording: 总数=%d 唯一名=%d' % (sum(c.values()),len(c)))
print('  集群侧同名多次(证明是上游固有):')
for k,v in sorted(c.items()):
    if v>1: print('    %-54s x%d' % (k,v))
"
echo
echo "===== [6] 其余容器未受影响 ====="
docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -i wxq
