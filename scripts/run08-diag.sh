#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== run-08 上卡住的 Pod 事件"
kubectl describe pod cilium-ltfgg -n kube-system 2>&1 | grep -A2 -E 'Warning|Failed|Pulling|Pulled' | tail -12
echo "=== run-08 containerd 状态"
timeout 30 ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@10.100.10.47 'systemctl is-active containerd kubelet; crictl images 2>/dev/null | grep -c cilium; crictl ps -a 2>/dev/null | grep -c cilium' 2>/dev/null
echo "=== run-08 磁盘空间"
timeout 20 ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@10.100.10.47 'df -h /var/lib/containerd /data1 2>/dev/null | tail -3' 2>/dev/null
echo "=== run-08 拉镜像测试（直接从 Harbor 拉 cilium）"
timeout 120 ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@10.100.10.47 'time crictl pull harbor.wuxing.local/cilium/cilium:v1.20.1 2>&1 | tail -3' 2>/dev/null
echo "=== run-08 containerd 最近日志"
timeout 20 ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@10.100.10.47 'journalctl -u containerd --since "10 min ago" --no-pager 2>/dev/null | grep -iE "error|warn" | tail -5' 2>/dev/null