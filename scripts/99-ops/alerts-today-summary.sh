#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
PP="prometheus-prometheus-stack-kube-prom-prometheus-0"
q() { kubectl -n monitoring exec $PP -c prometheus -- wget -qO- "http://localhost:9090/api/v1/query?query=$1" 2>/dev/null; }

echo "===== 1. 当前活跃告警全量 ====="
kubectl -n monitoring exec alertmanager-prometheus-stack-kube-prom-alertmanager-0 -c alertmanager -- \
  wget -qO- 'http://localhost:9093/api/v2/alerts?active=true&silenced=false' 2>/dev/null | python3 -c '
import sys, json
d = json.load(sys.stdin)
for a in sorted(d, key=lambda x: x.get("startsAt","")):
    l = a["labels"]
    print("  [%-8s] %-32s 开始=%s" % (l.get("severity"), l.get("alertname"), a.get("startsAt","")[:19].replace("T"," ")))
'
echo ""
echo "===== 2. KubeAggregatedAPIErrors 现状 ====="
q "ALERTS%7Balertname%3D%22KubeAggregatedAPIErrors%22%7D" 2>/dev/null | python3 -c '
import sys, json
d = json.load(sys.stdin)["data"]["result"]
if not d: print("  ✅ 已无该告警")
for r in d:
    m = r["metric"]
    print("  state=%s  aggregated=%s  since=%s" % (m.get("alertstate"), m.get("aggregated"), r.get("activeAt","")[:19]))
'
echo -n "  APIService custom.metrics: "
kubectl get apiservice v1beta1.custom.metrics.k8s.io -o jsonpath='{.status.conditions[0].type}={.status.conditions[0].status}' 2>/dev/null; echo ""
echo -n "  adapter Pod: "
kubectl -n monitoring get pods | grep adapter | awk '{print $2, $3, "重启="$4}' | tr '\n' ' '; echo ""
echo -n "  adapter 5xx(近10min): "
q "sum%20by%20(code)%20(rate(apiserver_request_total%7Burl%3D~%22.*custom.metrics.*%22%2Ccode%3D~%225..%22%7D%5B10m%5D))" 2>/dev/null | head -c 150; echo ""
echo ""
echo "===== 3. 今日全部告警时间线（今天触发过的所有告警）====="
kubectl -n monitoring exec alertmanager-prometheus-stack-kube-prom-alertmanager-0 -c alertmanager -- \
  wget -qO- 'http://localhost:9093/api/v2/alerts' 2>/dev/null | python3 -c '
import sys, json
from collections import Counter
d = json.load(sys.stdin)
c = Counter()
for a in d:
    c[(a["labels"].get("severity"), a["labels"].get("alertname"))] += 1
for (sev, name), n in sorted(c.items()):
    print("  [%-8s] %-32s 实例x%d" % (sev, name, n))
'