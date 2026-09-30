#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== CoreDNS Pod 状态"
kubectl get pods -n kube-system -l k8s-app=kube-dns -o wide 2>&1 | head -4
echo "=== DNS 解析测试（改前基线）"
kubectl run dnstest --image=harbor.wuxing.local/library/busybox:1.38.0 --restart=Never --command -- sh -c 'nslookup kubernetes.default.svc.cluster.local; echo RC=$?' 2>&1 | tail -1
sleep 15
kubectl logs dnstest 2>&1 | head -10
kubectl get pod dnstest --no-headers 2>&1
kubectl delete pod dnstest --force --grace-period=0 2>&1 | tail -1
echo "=== ClusterIP 连通测试（kube-dns 的 53 端口）"
kubectl run tcptest --image=harbor.wuxing.local/library/busybox:1.38.0 --restart=Never --command -- sh -c 'nc -zv -w3 10.233.0.10 53; echo RC=$?' 2>&1 | tail -1
sleep 12
kubectl logs tcptest 2>&1 | head -5
kubectl delete pod tcptest --force --grace-period=0 2>&1 | tail -1