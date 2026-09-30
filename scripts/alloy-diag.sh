#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
P=$(kubectl -n logging get pods -l app.kubernetes.io/name=alloy --no-headers 2>/dev/null | head -1 | awk "{print \$1}")
[ -z "$P" ] && P=$(kubectl -n logging get pods --no-headers 2>/dev/null | grep alloy | head -1 | awk "{print \$1}")
echo "Pod: $P"
echo "=== 日志 ==="
kubectl -n logging logs "$P" --tail=15 2>&1 | tail -12
echo "=== 上次终止原因 ==="
kubectl -n logging get pod "$P" -o jsonpath="{.status.containerStatuses[0].lastState.terminated.reason} exit={.status.containerStatuses[0].lastState.terminated.exitCode}" 2>&1; echo
echo "=== 用的配置文件 ==="
kubectl -n logging get cm --no-headers 2>/dev/null | grep -i alloy
kubectl -n logging get cm alloy -o jsonpath="{.data}" 2>/dev/null | head -c 400; echo