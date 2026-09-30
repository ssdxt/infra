#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
POD=$(kubectl get pods -n monitoring -l app.kubernetes.io/name=prometheus-node-exporter --no-headers 2>/dev/null | grep -E 'CrashLoop|Error' | head -1 | awk '{print $1}')
echo "=== 失败 Pod: $POD"
kubectl logs "$POD" -n monitoring --tail=15 2>&1 | tail -12
echo "=== 上次终止原因"
kubectl get pod "$POD" -n monitoring -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason} exit={.status.containerStatuses[0].lastState.terminated.exitCode}' 2>&1; echo
echo "=== operator 状态"
kubectl get pods -n monitoring -l app.kubernetes.io/name=prometheus-operator --no-headers 2>&1 | awk '{print $1, $2, $3}'