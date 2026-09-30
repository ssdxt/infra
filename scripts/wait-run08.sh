#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== run-08 上 Pod 状态"
kubectl get pods -n kube-system -o wide --no-headers 2>/dev/null | grep 'wxq-run-08'
echo "=== 全集群非Running"
kubectl get pods -A --no-headers 2>/dev/null | grep -v -E 'Running|Completed' | head -6 || echo ALL-RUNNING
echo "=== 节点"
kubectl get nodes --no-headers 2>&1 | awk '{print $1, $2}'
echo "=== KPR 状态"
kubectl -n kube-system exec ds/cilium -c cilium-agent -- cilium-dbg status 2>/dev/null | grep -E 'KubeProxyReplacement|Routing' | head -3