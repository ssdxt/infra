#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== Alertmanager 当前活跃告警 ====="
kubectl -n monitoring exec alertmanager-prometheus-stack-kube-prom-alertmanager-0 -c alertmanager -- \
  wget -qO- 'http://localhost:9093/api/v2/alerts?active=true&silenced=false&inhibited=false' 2>/dev/null | python3 -c '
import sys, json
d = json.load(sys.stdin)
if not d: print("  （无活跃告警 🎉）")
for a in d:
    l = a["labels"]
    ann = a.get("annotations", {})
    print("  [%s] %s" % (l.get("severity"), l.get("alertname")))
    print("     开始: %s" % a.get("startsAt","")[:19].replace("T"," "))
    for k in ("summary","description"):
        if ann.get(k): print("     %s: %s" % (k, ann[k][:160]))
    for k,v in sorted(l.items()):
        if k not in ("alertname","severity"): print("     %s=%s" % (k,v))
    print("")
'
echo "===== Prometheus 侧 pending 中的告警（还没到 for 时长）====="
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- \
  wget -qO- 'http://localhost:9090/api/v1/query?query=ALERTS%7Balertstate%3D%22pending%22%7D' 2>/dev/null | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)["data"]["result"]
    if not d: print("  （无 pending）")
    for r in d:
        m = r["metric"]
        print("  [pending] %s  %s" % (m.get("alertname"), {k:v for k,v in m.items() if k not in ("alertname","alertstate","severity")}))
except Exception as e: print("  查询失败:", e)
'
