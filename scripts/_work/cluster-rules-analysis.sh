#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== 各 PrometheusRule 的 groups 与规则数 ====="
kubectl -n monitoring get prometheusrule -o json | python3 -c "
import sys,json
d=json.load(sys.stdin)
tot=0; alerts=0; recs=0
rows=[]
for it in d['items']:
    n=it['metadata']['name']; gs=it['spec'].get('groups',[])
    a=sum(1 for g in gs for r in g.get('rules',[]) if 'alert' in r)
    rr=sum(1 for g in gs for r in g.get('rules',[]) if 'record' in r)
    tot+=a+rr; alerts+=a; recs+=rr
    rows.append((n,len(gs),a,rr))
for n,g,a,rr in sorted(rows):
    print('  %-62s groups=%-3d alerts=%-4d record=%-4d' % (n,g,a,rr))
print()
print('  合计: rules=%d (alerts=%d, recording=%d)' % (tot,alerts,recs))
"
echo
echo "===== 哪些规则表达式依赖 apiserver 指标(决定丢弃 apiserver 的影响面) ====="
kubectl -n monitoring get prometheusrule -o json | python3 -c "
import sys,json,re
d=json.load(sys.stdin)
hits={}
for it in d['items']:
    for g in it['spec'].get('groups',[]):
        for r in g.get('rules',[]):
            e=r.get('expr','')
            if re.search(r'apiserver_|APIServer|apiserver', e):
                hits.setdefault(r.get('alert') or r.get('record'),[]).append(it['metadata']['name'])
print('  依赖 apiserver_* 的规则共 %d 条:' % len(hits))
for k,v in sorted(hits.items()):
    print('    %-45s <- %s' % (k, v[0]))
"
echo
echo "===== 记录规则中是否有 apiserver 相关(cluster: 命名空间) ====="
kubectl -n monitoring get prometheusrule -o json | python3 -c "
import sys,json,re
d=json.load(sys.stdin)
for it in d['items']:
    for g in it['spec'].get('groups',[]):
        for r in g.get('rules',[]):
            if 'record' in r and re.search(r'apiserver', r.get('expr','')):
                print('  %-55s group=%s' % (r['record'], g['name']))
"
echo
echo "===== 告警规则总数(实际加载) 复核 ====="
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/rules?type=alert' 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']['groups']
print('  groups=%d alerts=%d' % (len(d), sum(len(g['rules']) for g in d)))
"
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/rules?type=record' 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']['groups']
print('  record groups=%d rules=%d' % (len(d), sum(len(g['rules']) for g in d)))
"
