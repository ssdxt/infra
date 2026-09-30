#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== Cilium ConfigMap 里 kube-proxy 相关"
kubectl get cm cilium-config -n kube-system -o json 2>/dev/null | python3 -c '
import sys, json
d = json.load(sys.stdin)["data"]
for k in sorted(d):
    if "kube-proxy" in k.lower() or "k8s-service" in k.lower():
        print(" ", k, "=", d[k])
'
echo "=== kube-proxy DaemonSet 是否还在"
kubectl get ds kube-proxy -n kube-system --no-headers 2>&1 | head -2
echo "=== cilium status 摘要"
kubectl exec -n kube-system ds/cilium -c cilium-agent -- cilium status --brief 2>/dev/null | head -3
echo "=== cilium-dbg 看 KPR 模式"
kubectl exec -n kube-system ds/cilium -c cilium-agent -- cilium-dbg status 2>/dev/null | grep -iE 'KubeProxyReplacement|Host firewall|Routing' | head -4