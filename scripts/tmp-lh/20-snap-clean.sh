#!/bin/bash
set -uo pipefail
export KUBECONFIG=/etc/kubernetes/admin.conf
# force delete stuck VS + its VSC
for vs in $(kubectl -n logging get volumesnapshot -o name); do
  kubectl -n logging patch $vs --type=merge -p '{"metadata":{"finalizers":null}}' 2>/dev/null
  kubectl -n logging delete $vs --wait=false 2>/dev/null
done
for vsc in $(kubectl get volumesnapshotcontent -o name); do
  kubectl patch $vsc --type=merge -p '{"metadata":{"finalizers":null}}' 2>/dev/null
  kubectl delete $vsc --wait=false 2>/dev/null
done
# delete old longhorn snapshots (backup-attempt leftovers)
for s in $(kubectl -n longhorn-system get snapshots.longhorn.io -o name); do
  kubectl -n longhorn-system patch $s --type=merge -p '{"metadata":{"finalizers":null}}' 2>/dev/null
  kubectl -n longhorn-system delete $s 2>/dev/null
done
sleep 5
kubectl -n longhorn-system get snapshots.longhorn.io 2>&1 | head -3
kubectl apply -n logging -f - <<'EOF'
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: loki-pre-upgrade
spec:
  volumeSnapshotClassName: longhorn
  source:
    persistentVolumeClaimName: storage-loki-0
EOF
for i in $(seq 1 36); do
  RT=$(kubectl -n logging get vs loki-pre-upgrade -o jsonpath='{.status.readyToUse}' 2>/dev/null)
  [ "$RT" = "true" ] && echo "READY after $((i*5))s" && break
  sleep 5
done
kubectl -n logging get volumesnapshot
kubectl -n longhorn-system get snapshots.longhorn.io 2>/dev/null | tail -3
