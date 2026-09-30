#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== 删除 kube-proxy（Cilium KPR 已接管）"
kubectl -n kube-system delete ds kube-proxy 2>&1 | tail -1
kubectl -n kube-system delete cm kube-proxy 2>&1 | tail -1
sleep 15
echo "=== 重建测试 Pod"
kubectl delete pod nettest --force --grace-period=0 2>/dev/null | tail -1
kubectl run nettest --image=harbor.wuxing.local/library/busybox:1.38.0 --restart=Never --command -- sleep 1800 2>&1 | tail -1
kubectl wait --for=condition=Ready pod/nettest --timeout=120s 2>&1 | tail -1
echo "=== 测试 ClusterIP (kubernetes 10.233.0.1:443)"
kubectl exec nettest -- nc -zv -w5 10.233.0.1 443 2>&1 | tail -2
echo "=== 测试 ClusterIP (kube-dns 10.233.0.10:53)"
kubectl exec nettest -- nc -zv -w5 10.233.0.10 53 2>&1 | tail -2
echo "=== 测试 DNS 解析"
kubectl exec nettest -- nslookup kubernetes.default.svc.cluster.local 2>&1 | tail -4
echo "=== gatewayclass 状态"
kubectl get gatewayclass 2>&1
kubectl get gatewayclass cilium -o jsonpath='{.status.conditions[0].status} {.status.conditions[0].reason}' 2>&1; echo