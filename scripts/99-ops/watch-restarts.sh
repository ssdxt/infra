#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
snap() { kubectl get pods -A -o json 2>/dev/null | python3 -c '
import sys, json, datetime
d = json.load(sys.stdin)
now = datetime.datetime.now(datetime.timezone.utc)
for p in d["items"]:
    md, st = p["metadata"], p["status"]
    tot = 0; last = None
    for cs in st.get("containerStatuses", []):
        tot += cs.get("restartCount", 0)
        lt = (cs.get("lastState") or {}).get("terminated") or {}
        f = lt.get("finishedAt")
        if f:
            try:
                t = datetime.datetime.fromisoformat(f.replace("Z","+00:00"))
                if last is None or t > last: last = t
            except Exception: pass
    if tot > 0:
        ago = (now-last).total_seconds()/60 if last else -1
        print("%s|%s|%d|%.1f" % (md["namespace"], md["name"], tot, ago))
'; }
echo "取基线..."
snap > /tmp/snap1.txt
echo "观察 5 分钟..."
sleep 300
snap > /tmp/snap2.txt
echo ""
echo "===== 5 分钟观察窗结果 ====="
python3 - <<'PY'
a = {}
for ln in open("/tmp/snap1.txt"):
    p = ln.strip().split("|")
    if len(p) == 4: a[(p[0], p[1])] = (int(p[2]), float(p[3]))
new_crash, growth = [], []
for ln in open("/tmp/snap2.txt"):
    p = ln.strip().split("|")
    if len(p) != 4: continue
    ns, name, tot, ago = p[0], p[1], int(p[2]), float(p[3])
    old = a.get((ns, name))
    if old is None:
        continue
    delta = tot - old[0]
    if delta > 0:
        growth.append((ns, name, old[0], tot, delta, ago))
print("5 分钟内新增崩溃的容器:")
if not growth:
    print("  ✅ 零新增 —— 换盘+恢复租约后，所有组件已停止崩溃")
for ns, name, o, n2, d2, ago in sorted(growth, key=lambda x: -x[4]):
    print("  %-14s %-44s %d→%d (+%d) 最近崩溃=%.0f分钟前" % (ns, name, o, n2, d2, ago))
print("")
print("全部历史重启大户当前状态:")
for ln in open("/tmp/snap2.txt"):
    p = ln.strip().split("|")
    if len(p) == 4 and int(p[2]) >= 40:
        print("  %-14s %-44s 累计=%-4s 最近一次崩溃=%.0f 分钟前" % (p[0], p[1], p[2], float(p[3])))
PY
echo ""
echo "===== 当前告警 ====="
kubectl -n monitoring exec alertmanager-prometheus-stack-kube-prom-alertmanager-0 -c alertmanager -- \
  wget -qO- 'http://localhost:9093/api/v2/alerts?active=true&silenced=false' 2>/dev/null | python3 -c '
import sys, json
from collections import Counter
d = json.load(sys.stdin)
c = Counter((a["labels"].get("severity"), a["labels"].get("alertname")) for a in d)
for (sev, name), n in sorted(c.items()): print("  [%s] %s x%d" % (sev, name, n))
'