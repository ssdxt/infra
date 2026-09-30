#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== 集群基线"
kubectl get nodes --no-headers 2>&1 | awk '{print $1, $2}' | tr '\n' ' '; echo
echo "=== 非Running Pod"
kubectl get pods -A --no-headers 2>/dev/null | grep -v -E 'Running|Completed' | head -4 || echo ALL-RUNNING
echo "=== Cilium 健康"
kubectl -n kube-system exec ds/cilium -c cilium-agent -- cilium-dbg status --brief 2>/dev/null | head -2
echo "=== 当前 cilium-config 关键项"
kubectl get cm cilium-config -n kube-system -o json 2>/dev/null | python3 -c '
import sys, json
d = json.load(sys.stdin)["data"]
for k in ("kube-proxy-replacement","k8s-service-host","k8s-service-port","routing-mode","tunnel-protocol","ipam","enable-gateway-api","bpf-masquerade","enable-ipv4","enable-ipv6","cluster-pool-ipv4-cidr"):
    if k in d: print("  ", k, "=", d[k])
'
echo "=== VIP/apiserver 可达性"
curl -sk -o /dev/null -w 'vip250=%{http_code}\n' --max-time 6 https://10.100.10.250:6443/healthz
echo "=== 服务测试基线（改前记录）"
kubectl -n kube-system get svc kube-dns -o jsonpath='{.spec.clusterIP}' 2>/dev/null; echo
kubectl run kpr-pre --image=harbor.wuxing.local/library/busybox:1.38.0 --restart=Never --rm -i --command -- nslookup kubernetes.default 2>&1 | tail -3