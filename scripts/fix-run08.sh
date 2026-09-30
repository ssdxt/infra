#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
NODE_IP=10.100.10.47
echo "=== run-08 当前镜像"
timeout 30 ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$NODE_IP 'crictl images 2>/dev/null | grep -E "cilium|REPOSITORY"' 2>/dev/null
echo "=== 删除损坏的镜像（触发重新拉取重建快照）"
timeout 60 ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$NODE_IP 'crictl rmi harbor.wuxing.local/cilium/cilium:v1.20.1 2>&1 | tail -2; crictl rmi harbor.wuxing.local/cilium/operator:v1.20.1 2>&1 | tail -1' 2>/dev/null
echo "=== 重启 containerd 清理快照元数据"
timeout 90 ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$NODE_IP 'systemctl stop kubelet; sleep 3; systemctl restart containerd; sleep 6; systemctl start kubelet; sleep 5; systemctl is-active containerd kubelet' 2>/dev/null
echo "=== 删除失败 Pod 让其重建"
kubectl delete pod -n kube-system cilium-2ftw7 cilium-envoy-vzkt6 cilium-operator-5c59b849dc-jwpl6 --force --grace-period=0 2>&1 | tail -3
echo "=== 等待 90 秒"
sleep 90
echo "=== run-08 上的 Pod 状态"
kubectl get pods -n kube-system -o wide --no-headers 2>/dev/null | grep 'wxq-run-08'
echo "=== 节点状态"
kubectl get nodes --no-headers 2>&1 | grep -v ' Ready '