#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== nodelocaldns 当前状态"
kubectl get pods -n kube-system -l k8s-app=nodelocaldns -o wide --no-headers 2>&1 | awk '{print $1, $2, $3, $5}' | head -12
echo "=== 取第一个未就绪 Pod 的日志"
POD=$(kubectl get pods -n kube-system -l k8s-app=nodelocaldns --no-headers 2>/dev/null | grep -vE '1/1 +Running' | head -1 | awk '{print $1}')
echo "pod=[$POD]"
if [ -n "$POD" ]; then
  kubectl logs "$POD" -n kube-system --tail=12 2>&1 | tail -10
  echo "=== 上次终止原因"
  kubectl get pod "$POD" -n kube-system -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason} {.status.containerStatuses[0].lastState.terminated.exitCode}' 2>&1; echo
fi
echo "=== DS 状态"
kubectl get ds nodelocaldns -n kube-system --no-headers 2>&1