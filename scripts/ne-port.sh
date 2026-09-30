#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== 谁在用 hostPort 9100"
kubectl get pods -A -o json 2>/dev/null | python3 -c '
import sys, json
d = json.load(sys.stdin)
for p in d["items"]:
    for c in p["spec"].get("containers", []) or []:
        for pt in c.get("ports", []) or []:
            if pt.get("hostPort") == 9100:
                print(" ", p["metadata"]["namespace"], p["metadata"]["name"], "img=", c["image"])
' 2>&1 | head -6
echo "=== 所有命名空间"
kubectl get ns --no-headers 2>&1 | awk '{print $1}' | tr '\n' ' '; echo
echo "=== 改 node-exporter 端口为 9101"
H=harbor.wuxing.local
helm upgrade prometheus-stack /data1/ssdxt/charts/kube-prometheus-stack-62.7.0.tgz -n monitoring --reuse-values \
  --set prometheus-node-exporter.service.port=9101 \
  --set prometheus-node-exporter.service.targetPort=9101 \
  --timeout 10m 2>&1 | tail -2
echo "=== 等 120 秒"
sleep 120
echo "=== node-exporter 状态"
kubectl get pods -n monitoring -l app.kubernetes.io/name=prometheus-node-exporter --no-headers 2>&1 | awk '{print $2, $3}' | sort | uniq -c
echo "=== monitoring 全部 Pod"
kubectl get pods -n monitoring --no-headers 2>&1 | awk '{print $1, $2, $3}' | head -20