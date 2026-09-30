#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
PP="prometheus-prometheus-stack-kube-prom-prometheus-0"
q() { kubectl -n monitoring exec $PP -c prometheus -- wget -qO- "http://localhost:9090/api/v1/query?query=$1" 2>/dev/null; }

echo "===== 1. 各窗口燃烧率（>1 就是在超标）====="
for w in 5m 30m 1h 6h; do
  echo -n "  burn_rate$w: "
  q "apiserver%3Aerror_budget%3Aburn_rate$w" 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)["data"]["result"]
    for r in d: print("%.3f" % float(r["value"][1]), end="  ")
    print("(空=无数据)" if not d else "")
except Exception as e: print("失败")
'
done
echo ""
echo "===== 2. apiserver 当前错误构成（最近5分钟）====="
q "sum%20by%20(code)%20(rate(apiserver_request_total%7Bcode%3D~%225..%7D%5B5m%5D))" 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)["data"]["result"]
    if not d: print("  5xx = 0 ✅")
    for r in d: print("  code=%s  %.2f/s" % (r["metric"].get("code"), float(r["value"][1])))
except Exception as e: print("  失败", e)
'
q "sum%20by%20(code)%20(rate(apiserver_request_total%7Bcode%3D%22429%22%7D%5B5m%5D))" 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)["data"]["result"]
    if not d: print("  429 = 0 ✅")
    for r in d: print("  429  %.2f/s" % float(r["value"][1]))
except Exception: print("  失败")
'
echo ""
echo "===== 3. 错误按 verb/resource 拆（5m，非2xx/3xx）====="
q "sum%20by%20(verb%2Cresource)%20(rate(apiserver_request_total%7Bcode%3D~%22429%7C5..%22%7D%5B5m%5D))" 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)["data"]["result"]
    rows=sorted(((r["metric"].get("verb"),r["metric"].get("resource"),float(r["value"][1])) for r in d), key=lambda x:-x[2])[:8]
    if not rows: print("  ✅ 无 429/5xx")
    for v,r2,rate in rows: print("  %-10s %-24s %.2f/s" % (v, r2 or "-", rate))
except Exception as e: print("  失败", e)
'
echo ""
echo "===== 4. etcd 健康 + 换盘后的慢写复查 ====="
for ip in 10.100.10.10 10.100.10.14 10.100.10.19; do
  echo -n "  [$ip] slow_fdatasync(最近10min)="
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$ip \
    'journalctl -u etcd --since "10 minutes ago" 2>/dev/null | grep -c "slow fdatasync"; echo -n "       election丢失="; journalctl -u etcd --since "10 minutes ago" 2>/dev/null | grep -cE "elected|became (candidate|leader)"' 2>/dev/null
done
echo ""
echo "===== 5. 当前谁在大量请求 apiserver（Top 客户端）====="
q "topk(8%2C%20sum%20by%20(userAgent)%20(rate(apiserver_request_total%5B5m%5D)))" 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)["data"]["result"]
    for r in d: print("  %-60s %.1f/s" % (r["metric"].get("userAgent","?")[:60], float(r["value"][1])))
except Exception as e: print("  失败", e)
'
echo ""
echo "===== 6. Longhorn 升级进行时？====="
helm list -n longhorn-system 2>/dev/null | sed 's/^/  /'
echo -n "  longhorn Pod 状态: "
kubectl -n longhorn-system get pods --no-headers 2>/dev/null | awk '{print $3}' | sort | uniq -c | tr '\n' ' '; echo
echo -n "  非 Running: "
kubectl -n longhorn-system get pods --no-headers 2>/dev/null | grep -vE "Running|Completed" | head -5 | awk '{print $1, $3}' | tr '\n' ' '; echo
echo ""
echo "===== 7. 最近 10 分钟重启的容器 ====="
kubectl get pods -A -o json 2>/dev/null | python3 -c '
import sys, json, datetime
d = json.load(sys.stdin)
now = datetime.datetime.now(datetime.timezone.utc)
hits = []
for p in d["items"]:
    for cs in p["status"].get("containerStatuses", []):
        lt = (cs.get("lastState") or {}).get("terminated") or {}
        f = lt.get("finishedAt")
        if f:
            try:
                t = datetime.datetime.fromisoformat(f.replace("Z","+00:00"))
                if (now-t).total_seconds() < 600:
                    hits.append(("%.0f分钟前" % ((now-t).total_seconds()/60), p["metadata"]["namespace"], p["metadata"]["name"], lt.get("reason"), lt.get("exitCode")))
            except Exception: pass
hits.sort()
if not hits: print("  ✅ 最近 10 分钟无容器崩溃")
for h in hits[:15]: print("  %-10s %s/%s  %s exit=%s" % (h[0], h[1], h[2], h[3], h[4]))
'