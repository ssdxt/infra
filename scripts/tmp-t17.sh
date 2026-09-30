#!/bin/bash
# Install Alloy
set -u
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== install alloy ==="
bash /data1/ssdxt/logging/02-alloy.sh 2>&1 | tail -14
echo ""
echo "=== wait 90s ==="
sleep 90
echo "=== daemonset ==="
kubectl -n logging get ds 2>&1
echo "=== pods ==="
kubectl -n logging get pods -o wide 2>&1
echo "=== alloy images in use ==="
kubectl -n logging get ds alloy -o jsonpath='{.spec.template.spec.containers[*].image}' 2>&1
echo ""
echo "=== alloy configmap content head ==="
kubectl -n logging get cm alloy -o jsonpath='{.data.config\.alloy}' 2>&1 | head -20
echo ""
echo "=== alloy logs (one pod) ==="
P=$(kubectl -n logging get pods -l app.kubernetes.io/name=alloy --no-headers 2>/dev/null | awk '{print $1}' | head -1)
[ -z "$P" ] && P=$(kubectl -n logging get pods --no-headers | grep alloy | awk '{print $1}' | head -1)
echo "pod=$P"
kubectl -n logging logs $P --tail=20 2>&1
