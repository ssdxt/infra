#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== 当前告警汇总（Alertmanager）==="
kubectl -n monitoring exec alertmanager-prometheus-stack-kube-prom-alertmanager-0 -c alertmanager -- \
  wget -qO- http://localhost:9093/api/v2/alerts 2>/dev/null | python3 -c '
import sys, json
from collections import Counter
d = json.load(sys.stdin)
c = Counter((a["labels"].get("severity"), a["labels"].get("alertname")) for a in d)
if not c: print("  （无告警）")
for (sev, name), n in sorted(c.items()):
    print("  [%-8s] %-32s x%d" % (sev, name, n))
'
echo ""
echo "=== NodeClockNotSynchronising 明细（Prometheus）==="
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- \
  wget -qO- 'http://localhost:9090/api/v1/query?query=ALERTS%7Balertname%3D%22NodeClockNotSynchronising%22%7D' 2>/dev/null | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)["data"]["result"]
    if not d:
        print("  ✅ 该告警已完全消失")
    else:
        for r in d:
            print("  %-18s state=%s" % (r["metric"].get("instance","?"), r["metric"].get("alertstate")))
except Exception as e:
    print("  查询失败:", e)
'
echo ""
echo "=== 复核同步状态 ==="
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- \
  wget -qO- 'http://localhost:9090/api/v1/query?query=node_timex_sync_status' 2>/dev/null | python3 -c '
import sys, json
d = json.load(sys.stdin)["data"]["result"]
ones = sum(1 for r in d if r["value"][1] == "1")
print("  同步: %d / %d 台" % (ones, len(d)))
'
echo ""
echo "=== 节点间时钟偏差（各节点 System time 偏移）==="
for ip in 10.100.10.10 10.100.10.19 10.100.10.33; do
  echo -n "  [$ip] "
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=6 root@$ip \
    'chronyc tracking 2>/dev/null | grep -E "System time|Last offset" | tr "\n" " "' 2>/dev/null
  echo
done
