#!/bin/bash
P=http://127.0.0.1:9091
echo "===== 等待规则完成首轮求值(120s) ====="
sleep 120
echo
echo "===== [1] 规则健康度(重启后应全部 ok) ====="
curl -s "$P/api/v1/rules" | python3 -c "
import sys,json
from collections import Counter
d=json.load(sys.stdin)['data']['groups']
c=Counter()
for g in d:
    for r in g['rules']: c[(r['type'],r.get('health'))]+=1
print('  groups=%d rules=%d' % (len(d),sum(len(g['rules']) for g in d)))
for k,v in sorted(c.items()): print('    %-26s %s' % (str(k),v))
bad=[(r['name'],g['name'],r.get('health'),(r.get('lastError') or '')[:120]) for g in d for r in g['rules'] if r.get('health')!='ok']
print()
if bad:
    print('  仍有 %d 条非 ok:' % len(bad))
    for n,g,h,e in bad: print('    %-52s group=%-40s %-8s %s' % (n,g,h,e))
else:
    print('  ✅ 全部规则 health=ok')
"
echo
echo "===== [2] 'unknown' 的原因: 多阶段 recording 依赖链 ====="
curl -s "$P/api/v1/rules" | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']['groups']
for g in d:
    if 'apiserver-availability' not in g['name']: continue
    print('  group:',g['name'],' health分布:',end=' ')
    from collections import Counter
    print(dict(Counter(r.get('health') for r in g['rules'])))
    for r in g['rules']:
        print('    %-58s %-8s evalTime=%s' % (r['name'], r.get('health'), r.get('evaluationTime')))
"
echo
echo "===== [3] 上游依赖是否已产出(availability30d 依赖 count:increase30d) ====="
for m in 'cluster_verb_scope:apiserver_request_sli_duration_seconds_count:increase30d' 'apiserver_request:availability30d'; do
  printf '  %-66s = ' "$m"
  curl -s --get "$P/api/v1/query" --data-urlencode "query=count($m)" | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print(r[0]['value'][1] if r else '无数据')"
done
echo
echo "  ^ 若 increase30d 有数据而 availability30d 也有, 说明链路已通"
echo
echo "===== [4] 集群规则是否在正常求值(抽样看 lastEvaluation) ====="
curl -s "$P/api/v1/rules" | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']['groups']
new=[g for g in d if g.get('file','').endswith('cluster-wxq-rules.yaml')]
print('  cluster-wxq-rules.yaml 的 %d 个组:' % len(new))
for g in new[:6]:
    print('    %-46s interval=%-6s lastEval=%s evalTime=%s' % (g['name'],g.get('interval'),g.get('lastEvaluation'),g.get('evaluationTime')))
"
echo
echo "===== [5] 告警是否正常路由到 alertmanager ====="
curl -s 'http://127.0.0.1:9093/api/v2/alerts' | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    print('  Alertmanager 当前告警 = %d 条' % len(d))
    for a in d[:10]:
        print('    -',a['labels'].get('alertname'),'| severity=',a['labels'].get('severity'),'| instance_name=',a['labels'].get('instance_name'))
except Exception as e: print('  ERR',e)
"
echo
echo "===== [6] 本地 remote_write 到 VM 仍正常 ====="
curl -s --get "$P/api/v1/query" --data-urlencode 'query=prometheus_remote_storage_samples_total' | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
for x in r: print('  %s = %s' % (x['metric'].get('url'), x['value'][1]))
"
echo
echo "===== [7] 无 error 日志 ====="
docker logs wxq-prometheus --tail 150 2>&1 | grep -iE 'level=error|panic|fatal' || echo "  ✅ 无 error/panic/fatal"
