#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== 日志体系 ==="
kubectl -n logging get pods --no-headers 2>/dev/null | awk '{print "  "$1, $2, $3, $10}'
echo "=== Longhorn 异常 Pod ==="
kubectl -n longhorn-system get pods --no-headers 2>/dev/null | grep -v -E '1/1|2/2|3/3' | awk '{print "  "$1, $2, $3}'
echo "=== 全集群非Running ==="
kubectl get pods -A --no-headers 2>/dev/null | grep -v -E 'Running|Completed' | awk '{print "  "$1, $2, $3}' | head -6
echo "=== PVC（Loki 的）==="
kubectl get pvc -n logging --no-headers 2>/dev/null || echo "  无"
echo "=== 节点 ==="
kubectl get nodes --no-headers | awk '{print $2}' | sort | uniq -c