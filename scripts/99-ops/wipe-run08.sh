#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
N=10.100.10.47
echo "=== run-08 系统盘空间"
timeout 20 ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$N 'df -h / /var/lib/containerd 2>/dev/null | tail -2; du -sh /var/lib/containerd 2>/dev/null' 2>/dev/null
echo "=== 清空 containerd 状态（保留配置）"
timeout 180 ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$N 'systemctl stop kubelet; sleep 3; systemctl stop containerd; sleep 5; rm -rf /var/lib/containerd/*; sleep 2; systemctl start containerd; sleep 10; ls /var/lib/containerd/io.containerd.snapshotter.v1.overlayfs/ 2>&1 | head -3; systemctl start kubelet; sleep 5; systemctl is-active containerd kubelet' 2>/dev/null
echo "=== 等待 100 秒后看 run-08 状态"
sleep 100
kubectl get pods -n kube-system -o wide --no-headers 2>/dev/null | grep 'wxq-run-08'
kubectl get nodes --no-headers 2>&1 | grep -v ' Ready ' || echo "全部 Ready"