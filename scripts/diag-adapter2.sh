#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== adapter 崩溃原因 ====="
kubectl -n monitoring get pods -o json | python3 -c '
import sys, json, datetime
d = json.load(sys.stdin)
now = datetime.datetime.now(datetime.timezone.utc)
for p in d["items"]:
    if "adapter" not in p["metadata"]["name"]: continue
    print("  Pod:", p["metadata"]["name"], " phase:", p["status"]["phase"])
    for cs in p["status"].get("containerStatuses", []):
        print("    restartCount:", cs.get("restartCount"), " ready:", cs.get("ready"))
        lt = (cs.get("lastState") or {}).get("terminated") or {}
        if lt:
            print("    上次退出:", lt.get("reason"), "exit=", lt.get("exitCode"), "at", str(lt.get("finishedAt"))[:19])
'
echo ""
echo "--- 当前 Pod 内存限额 vs 实际"
kubectl -n monitoring get deploy prometheus-adapter -o jsonpath='limits: {.spec.template.spec.containers[0].resources.limits}  requests: {.spec.template.spec.containers[0].resources.requests}{"\n"}' 2>/dev/null
kubectl -n monitoring top pods 2>/dev/null | grep adapter | sed 's/^/  /'
echo ""
echo "--- 崩溃前后日志（OOM 还是 probe）"
P=$(kubectl -n monitoring get pods --no-headers 2>/dev/null | grep adapter | head -1 | awk '{print $1}')
kubectl -n monitoring logs $P --previous --tail=15 2>/dev/null | tail -10 | sed 's/^/  /'
echo ""
echo "--- describe 关键事件"
kubectl -n monitoring describe pod $P 2>/dev/null | grep -A2 -E "Last State|Reason|OOM|Killing|Unhealthy" | head -15 | sed 's/^/  /'
echo ""
echo "--- APIService 注册的服务后端"
kubectl -n monitoring get svc prometheus-adapter -o wide 2>/dev/null | sed 's/^/  /'
kubectl get endpointslices -A 2>/dev/null | grep custom.metrics | head -2 | sed 's/^/  /'