#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== install metrics-server ==="
bash /data1/ssdxt/monitoring/01-metrics-server.sh 2>&1 | tail -12
echo ""
echo "=== waiting 75s ==="
sleep 75
echo "=== pods ==="
kubectl -n kube-system get pods -l k8s-app=metrics-server -o wide
echo "=== apiservice ==="
kubectl get apiservice v1beta1.metrics.k8s.io -o wide 2>&1
echo "=== top nodes ==="
kubectl top nodes 2>&1
echo "=== top pods -A (head) ==="
kubectl top pods -A 2>&1 | head -12
