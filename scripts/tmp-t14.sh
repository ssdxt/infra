#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== helm status loki ==="
helm -n logging list 2>&1
helm -n logging status loki 2>&1 | head -20
echo ""
echo "=== all resources in logging ==="
kubectl -n logging get all 2>&1
echo ""
echo "=== statefulsets ==="
kubectl -n logging get statefulset loki -o yaml 2>&1 | grep -E 'replicas|image:|storageClassName|kind: StatefulSet' | head -20
echo ""
echo "=== events in logging ==="
kubectl -n logging get events --sort-by=.lastTimestamp 2>&1 | tail -20
echo ""
echo "=== snapshot CRDs present? ==="
kubectl get crd 2>&1 | grep -i snapshot || echo "  NONE - VolumeSnapshot CRDs missing"
echo ""
echo "=== longhorn chart: snapshot-related values ==="
helm -n longhorn-system show values longhorn 2>/dev/null | grep -n -i -B2 -A4 'snapshot' | head -40
echo ""
echo "=== longhorn manager setting: csi / snapshot toggles ==="
kubectl -n longhorn-system get settings.longhorn.io 2>/dev/null | grep -i -E 'csi|snapshot' | head
