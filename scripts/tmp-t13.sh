#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== install loki ==="
bash /data1/ssdxt/logging/01-loki.sh 2>&1 | tail -20
echo "EXIT=$?"
echo ""
echo "=== pods ==="
kubectl -n logging get pods -o wide 2>&1
echo "=== pvc ==="
kubectl -n logging get pvc 2>&1
echo "=== svc ==="
kubectl -n logging get svc 2>&1
