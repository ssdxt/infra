#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== Cilium agent pods"
kubectl get pods -n kube-system -l k8s-app=cilium --no-headers 2>&1 | awk '{print $1, $2, $3, $5}' | head -12
echo "=== operator"
kubectl get pods -n kube-system -l io.cilium/app=operator --no-headers 2>&1 | awk '{print $1, $2, $3}' | head -4
echo "=== KPR 状态"
kubectl -n kube-system exec ds/cilium -c cilium-agent -- cilium-dbg status 2>/dev/null | grep -E 'KubeProxyReplacement|Routing|Host firewall' | head -4
echo "=== 节点"
kubectl get nodes --no-headers 2>&1 | awk '{print $2}' | sort | uniq -c
echo "=== 非Running"
kubectl get pods -A --no-headers 2>/dev/null | grep -v -E 'Running|Completed' | head -5 || echo ALL-RUNNING
echo "=== gatewayclass"
kubectl get gatewayclass 2>&1
echo "=== kube-proxy 是否还在"
kubectl get ds kube-proxy -n kube-system --no-headers 2>&1 | head -1