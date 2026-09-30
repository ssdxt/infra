#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== agent 是否有 k8s-service-host 参数"
kubectl get ds cilium -n kube-system -o jsonpath='{.spec.template.spec.containers[0].args}' 2>&1 | tr ',' '\n' | grep -iE 'k8s-service|kube-proxy' | head -5
echo "=== operator 参数"
kubectl get deploy cilium-operator -n kube-system -o jsonpath='{.spec.template.spec.containers[0].args}' 2>&1 | tr ',' '\n' | grep -iE 'k8s-service|kube-proxy|gateway' | head -5
echo "=== 滚动重启 cilium agent（让 KPR 生效）"
kubectl -n kube-system rollout restart ds/cilium 2>&1 | tail -1
kubectl -n kube-system rollout restart deploy/cilium-operator 2>&1 | tail -1
echo "=== 等待滚动完成（最多 8 分钟）"
kubectl -n kube-system rollout status ds/cilium --timeout=480s 2>&1 | tail -2
kubectl -n kube-system rollout status deploy/cilium-operator --timeout=180s 2>&1 | tail -1
echo "=== KPR 状态确认"
kubectl -n kube-system exec ds/cilium -c cilium-agent -- cilium-dbg status 2>/dev/null | grep -E 'KubeProxyReplacement|Routing|Host firewall' | head -4