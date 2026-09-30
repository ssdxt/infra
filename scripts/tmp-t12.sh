#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== csi-snapshotter pods ==="
kubectl -n longhorn-system get pods -l app=csi-snapshotter -o wide 2>&1
echo ""
echo "=== the Error pod: describe tail ==="
POD=$(kubectl -n longhorn-system get pods -l app=csi-snapshotter --field-selector=status.phase=Failed -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
[ -z "$POD" ] && POD=$(kubectl -n longhorn-system get pods --no-headers 2>/dev/null | awk '$3=="Error"{print $1}' | head -1)
echo "pod=$POD"
kubectl -n longhorn-system describe pod $POD 2>&1 | tail -25
echo ""
echo "=== its current logs ==="
kubectl -n longhorn-system logs $POD --tail=20 2>&1
echo ""
echo "=== its previous (crashed) logs ==="
kubectl -n longhorn-system logs $POD --previous --tail=25 2>&1
