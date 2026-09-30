#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== control-01 上的 python/yaml 能力 ====="
python3 -V
python3 -c 'import yaml; print("pyyaml", yaml.__version__)' 2>&1 | head -2
python3 -c 'import json; print("json OK")'
echo
echo "===== 导出 PrometheusRule 为 JSON(原生格式,后续转换用) ====="
kubectl -n monitoring get prometheusrule -o json > /tmp/cluster-rules-all.json
echo "  /tmp/cluster-rules-all.json  $(wc -c < /tmp/cluster-rules-all.json) bytes"
echo
echo "===== 集群 recording 规则名 与 plant01 现有规则名 冲突检查(集群侧先列出) ====="
python3 - <<'PY'
import json
d=json.load(open('/tmp/cluster-rules-all.json'))
recs=set(); alerts=set()
for it in d['items']:
    for g in it['spec'].get('groups',[]):
        for r in g.get('rules',[]):
            if 'record' in r: recs.add(r['record'])
            if 'alert'  in r: alerts.add(r['alert'])
print('  集群 recording 规则名 (%d):' % len(recs))
for x in sorted(recs): print('    ', x)
print()
print('  集群 alert 规则名 (%d), 抽样:' % len(alerts))
for x in sorted(alerts)[:12]: print('    ', x)
PY
