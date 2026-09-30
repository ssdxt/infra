#!/bin/bash
set -uo pipefail
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== errors in leader log"
kubectl -n longhorn-system logs csi-snapshotter-5467bbccf-kd2w8 2>&1 | grep -E '^E|error|failed' | tail -10
echo "=== restart deployment"
kubectl -n longhorn-system rollout restart deploy/csi-snapshotter
kubectl -n longhorn-system rollout status deploy/csi-snapshotter --timeout=180s
echo "=== recreate snapshot"
kubectl -n logging delete volumesnapshot loki-pre-upgrade-20260930 --wait=false 2>/dev/null
sleep 5
cat <<EOF | kubectl -n logging apply -f -
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
kubectl -n logging describe volumesnapshot loki-pre-upgrade | tail -12
kubectl -n longhorn-system get snapshots.longhorn.io 2>/dev/null
