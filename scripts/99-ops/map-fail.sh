#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== 失败 Pod 与节点映射"
kubectl get pods -n kube-system --no-headers -o wide 2>/dev/null | grep -E 'CreateContainerError|Init:' | awk '{print $1, $3, $7}'
echo "=== run-08 状态详情"
kubectl describe node wxq-run-08 2>&1 | grep -E 'Ready|MemoryPressure|DiskPressure|KubeletNotReady' | head -5
echo "=== run-08 上 kubelet/cilium 情况"
timeout 20 ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@10.100.10.47 'systemctl is-active kubelet containerd; ls /etc/kubernetes/kubelet.conf 2>/dev/null && echo has-kubelet-conf; crictl ps 2>/dev/null | head -3' 2>/dev/null