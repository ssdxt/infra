#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== 修复 HTTPRoute CRD（server-side apply）"
cd /data1/ssdxt/charts/gateway-api
kubectl apply --server-side --force-conflicts -f experimental-install.yaml 2>&1 | grep -E 'httproutes|configured|created' | tail -3
echo "=== 部署 nodelocaldns"
kubectl apply -f /data1/ssdxt/charts/nodelocaldns.yaml 2>&1 | tail -6
echo "=== 等待 60 秒"
sleep 60
echo "=== nodelocaldns Pod 状态"
kubectl get pods -n kube-system -l k8s-app=nodelocaldns --no-headers 2>&1 | awk '{print $1, $2, $3}' | head -12