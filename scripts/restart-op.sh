#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== 重启 operator"
kubectl -n kube-system rollout restart deploy/cilium-operator 2>&1 | tail -1
kubectl -n kube-system rollout status deploy/cilium-operator --timeout=240s 2>&1 | tail -1
sleep 45
echo "=== gatewayclass"
kubectl get gatewayclass 2>&1
kubectl get gatewayclass cilium -o jsonpath='{.status.conditions[0].status} / {.status.conditions[0].reason}' 2>&1; echo
echo "=== operator 日志里 gateway 控制器启动迹象"
kubectl logs -n kube-system -l io.cilium/app=operator --tail=120 2>/dev/null | grep -iE 'gateway' | tail -6