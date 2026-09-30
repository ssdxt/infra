#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== metrics-server logs (tail 40) ==="
kubectl -n kube-system logs deploy/metrics-server --tail=40 2>&1
echo ""
echo "=== raw metrics API /nodes ==="
kubectl get --raw "/apis/metrics.k8s.io/v1beta1/nodes" 2>&1 | head -c 600
echo ""
echo "=== raw /version ==="
kubectl get --raw "/apis/metrics.k8s.io/v1beta1" 2>&1 | head -c 600
echo ""
echo "=== describe apiservice ==="
kubectl describe apiservice v1beta1.metrics.k8s.io 2>&1 | tail -20
echo ""
echo "=== endpoints ==="
kubectl -n kube-system get endpoints metrics-server -o wide 2>&1
echo ""
echo "=== can apiserver reach? try from a pod ==="
kubectl -n kube-system run nettest-$RANDOM --rm -i --restart=Never --image=harbor.wuxing.local/library/busybox:1.38.0 --timeout=60s -- wget -qO- --timeout=8 https://metrics-server.kube-system.svc:443/livez --no-check-certificate 2>&1 | head -5
echo ""
echo "=== ciliumnetworkpolicies ==="
kubectl get cnp -A 2>&1 | head -20
echo "=== kubelet port check on one node ==="
timeout 8 curl -sk https://10.100.10.33:10250/healthz 2>&1 | head -2
