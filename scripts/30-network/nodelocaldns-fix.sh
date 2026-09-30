#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== 重新应用修正后的 nodelocaldns"
kubectl apply -f /data1/ssdxt/charts/nodelocaldns.yaml 2>&1 | grep -E 'daemonset|configmap' | tail -2
echo "=== 删除旧 Pod 让其重建"
kubectl delete pods -n kube-system -l k8s-app=nodelocaldns --force --grace-period=0 2>&1 | tail -2
echo "=== 等待 120 秒"
sleep 120
echo "=== nodelocaldns 状态"
kubectl get pods -n kube-system -l k8s-app=nodelocaldns --no-headers 2>&1 | awk '{print $2, $3}' | sort | uniq -c
echo "=== DNS 解析测试"
kubectl delete pod nettest --force --grace-period=0 2>/dev/null | tail -1
kubectl run nettest --image=harbor.wuxing.local/library/busybox:1.38.0 --restart=Never --command -- sleep 600 2>&1 | tail -1
kubectl wait --for=condition=Ready pod/nettest --timeout=120s 2>&1 | tail -1
kubectl exec nettest -- nslookup kubernetes.default.svc.cluster.local 2>&1 | tail -5