#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
POD=$(kubectl get pods -n kube-system -l k8s-app=nodelocaldns --no-headers 2>/dev/null | grep Error | head -1 | awk '{print $1}')
echo "=== 失败 Pod: $POD"
kubectl logs $POD -n kube-system --tail=20 2>&1 | tail -15
echo "=== describe 关键错误"
kubectl describe pod $POD -n kube-system 2>&1 | grep -A3 -E 'Last State|Reason|Message' | head -12