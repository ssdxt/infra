#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== 创建长驻测试 Pod"
kubectl run nettest --image=harbor.wuxing.local/library/busybox:1.38.0 --restart=Never --command -- sleep 3600 2>&1 | tail -1
kubectl wait --for=condition=Ready pod/nettest --timeout=120s 2>&1 | tail -1
echo "=== Pod IP 与所在节点"
kubectl get pod nettest -o wide --no-headers 2>&1
echo "=== 测试1: Pod 内 gateway/路由"
kubectl exec nettest -- ip route 2>&1 | head -5
echo "=== 测试2: 解析 DNS 配置"
kubectl exec nettest -- cat /etc/resolv.conf 2>&1 | head -4
echo "=== 测试3: 直连 CoreDNS Pod IP (10.233.68.210:53)"
kubectl exec nettest -- nc -zv -w3 10.233.68.210 53 2>&1 | tail -2
echo "=== 测试4: 连 kube-dns ClusterIP 10.233.0.10:53"
kubectl exec nettest -- nc -zv -w3 10.233.0.10 53 2>&1 | tail -2
echo "=== 测试5: 连 kubernetes ClusterIP 10.233.0.1:443"
kubectl exec nettest -- nc -zv -w3 10.233.0.1 443 2>&1 | tail -2
echo "=== kube-proxy 模式与日志"
kubectl get ds kube-proxy -n kube-system -o jsonpath='{.spec.template.spec.containers[0].command}' 2>&1; echo
kubectl logs -n kube-system -l k8s-app=kube-proxy --tail=3 2>&1 | tail -4