#!/bin/bash
# Install external-snapshotter CRDs (Longhorn CSI snapshotter prerequisite)
set -u
export KUBECONFIG=/etc/kubernetes/admin.conf
D=/data1/ssdxt/storage/crds
mkdir -p $D
cp -n /tmp/snapshot.storage.k8s.io_*.yaml $D/ 2>/dev/null
echo "=== CRD files staged ==="
ls -la $D/

echo ""
echo "=== apply CRDs ==="
kubectl apply -f $D/ 2>&1

echo ""
echo "=== verify CRDs ==="
kubectl get crd 2>&1 | grep -i 'snapshot.storage.k8s.io'

echo ""
echo "=== wait 100s and re-check csi-snapshotter ==="
sleep 100
kubectl -n longhorn-system get pods -l app=csi-snapshotter 2>&1
echo "--- current logs of one ---"
P=$(kubectl -n longhorn-system get pods -l app=csi-snapshotter --no-headers | awk '{print $1}' | head -1)
kubectl -n longhorn-system logs $P --tail=8 2>&1
