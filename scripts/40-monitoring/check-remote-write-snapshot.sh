#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== remote_write 到 plant01 的状态（新出现的 pending 告警）====="
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- sh -c \
 "wget -qO- 'http://localhost:9090/api/v1/query?query=prometheus_remote_storage_samples_pending' 2>/dev/null; echo; wget -qO- 'http://localhost:9090/api/v1/query?query=prometheus_remote_storage_samples_failed_total' 2>/dev/null" 2>/dev/null | python3 -c '
import sys,json
data=sys.stdin.read().split("\n")
for part in data:
    part=part.strip()
    if not part: continue
    try:
        d=json.loads(part)["data"]["result"]
        for r in d:
            print("  %s = %s" % (r["metric"].get("__name__"), r["value"][1]))
    except Exception: pass
'
echo -n "  plant01:9091 /-/ready : "
curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://10.100.10.29:9091/-/ready; echo
echo -n "  plant01:9091 count(up) : "
curl -s --max-time 8 'http://10.100.10.29:9091/api/v1/query?query=count(up)' 2>/dev/null | head -c 150; echo
echo ""
echo "===== csi-snapshotter Deployment（longhorn-system）====="
kubectl -n longhorn-system get deploy csi-snapshotter -o wide 2>/dev/null | sed 's/^/  /' || echo "  无此 deployment"
kubectl -n longhorn-system get pods 2>/dev/null | grep -i snapshot | sed 's/^/  /'
echo ""
echo "===== cilium-operator 两个副本状态 ====="
kubectl -n kube-system get pods -l io.cilium/app=operator -o wide 2>/dev/null | sed 's/^/  /'
