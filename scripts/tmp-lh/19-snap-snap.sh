#!/bin/bash
set -uo pipefail
export KUBECONFIG=/etc/kubernetes/admin.conf
kubectl -n logging wait --for=delete volumesnapshot/loki-pre-upgrade --timeout=60s 2>/dev/null
kubectl -n logging apply -f - <<'EOF'
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: loki-pre-upgrade
spec:
  volumeSnapshotClassName: longhorn
  source:
    persistentVolumeClaimName: storage-loki-0
EOF
for i in $(seq 1 30); do
  RT=$(kubectl -n logging get vs loki-pre-upgrade -o jsonpath='{.status.readyToUse}' 2>/dev/null)
  [ "$RT" = "true" ] && echo "READY after $((i*5))s" && break
  sleep 5
done
kubectl -n logging get volumesnapshot
kubectl -n longhorn-system get snapshots.longhorn.io | tail -3
