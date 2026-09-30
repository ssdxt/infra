#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== operator Pod 位置与状态"
kubectl get pods -n monitoring --no-headers -o wide 2>&1 | grep operator
echo "=== operator 事件"
POD=$(kubectl get pods -n monitoring --no-headers 2>/dev/null | grep operator | head -1 | awk '{print $1}')
kubectl describe pod "$POD" -n monitoring 2>&1 | grep -A2 -E 'Warning|Failed|Pulling|Pulled|Created' | tail -10
echo "=== 该节点 containerd 是否正常"
NODE=$(kubectl get pod "$POD" -n monitoring -o jsonpath='{.spec.nodeName}' 2>/dev/null)
echo "node=$NODE"