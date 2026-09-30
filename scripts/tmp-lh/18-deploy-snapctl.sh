#!/bin/bash
set -uo pipefail
export KUBECONFIG=/etc/kubernetes/admin.conf
kubectl apply -f /data1/ssdxt/storage/crds/rbac-snapshot-controller.yaml
kubectl apply -f /data1/ssdxt/storage/snapshot-controller.yaml
kubectl -n longhorn-system rollout status deploy/snapshot-controller --timeout=180s
sleep 10
echo "== retry snapshot"
kubectl -n logging delete volumesnapshot loki-pre-upgrade --wait=false 2>/dev/null
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
for i in $(seq 1 30); do
  RT=$(kubectl -n logging get vs loki-pre-upgrade -o jsonpath='{.status.readyToUse}' 2>/dev/null)
  [ "$RT" = "true" ] && echo "READY after $((i*5))s" && break
  sleep 5
done
kubectl -n logging get volumesnapshot
kubectl -n longhorn-system get snapshots.longhorn.io 2>/dev/null
