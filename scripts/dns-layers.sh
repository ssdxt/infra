#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== CoreDNS 的 Corefile（第二层，权威解析）"
kubectl get cm coredns -n kube-system -o jsonpath='{.data.Corefile}' 2>&1
echo ""
echo "=== nodelocaldns 的 Corefile（第一层，节点本地缓存）"
kubectl get cm nodelocaldns -n kube-system -o jsonpath='{.data.Corefile}' 2>&1
echo ""
echo "=== CoreDNS 副本数与 Service"
kubectl get deploy coredns -n kube-system --no-headers 2>&1
kubectl get svc kube-dns -n kube-system --no-headers 2>&1
echo "=== nodelocaldns 上游自动探测结果（日志）"
POD=$(kubectl get pods -n kube-system -l k8s-app=nodelocaldns --no-headers 2>/dev/null | head -1 | awk '{print $1}')
kubectl logs "$POD" -n kube-system --tail=6 2>&1 | tail -6
echo "=== Pod 实际用的解析器"
kubectl run dnscheck --image=harbor.wuxing.local/library/busybox:1.38.0 --restart=Never --command -- sleep 300 2>&1 | tail -1
kubectl wait --for=condition=Ready pod/dnscheck --timeout=90s 2>&1 | tail -1
kubectl exec dnscheck -- cat /etc/resolv.conf 2>&1