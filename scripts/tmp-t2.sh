#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== nodes ==="
kubectl get nodes -o wide
echo "=== version ==="
kubectl version -o yaml 2>/dev/null | grep -E 'gitVersion' | head -4
echo "=== storageclass ==="
kubectl get sc
echo "=== namespaces ==="
kubectl get ns
echo "=== charts ==="
ls -la /data1/ssdxt/charts/
echo "=== helm releases ==="
helm list -A
echo "=== iscsi status (this node) ==="
dpkg -l | grep -E 'open-iscsi|iscsid' || echo "no open-iscsi"
echo "=== containerd harbor CA ==="
ls -la /etc/containerd/certs.d/harbor.wuxing.local/ 2>&1
echo "=== data1 ==="
df -h /data1