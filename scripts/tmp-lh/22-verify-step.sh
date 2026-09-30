#!/bin/bash
set -uo pipefail
export KUBECONFIG=/etc/kubernetes/admin.conf
for i in $(seq 1 40); do
  N=$(kubectl -n longhorn-system get pods --no-headers | grep -vE '^[a-zA-Z0-9-]+\s+[0-9]+/[0-9]+\s+Running' | grep -cv Completed)
  [ "$N" = "0" ] && break
  sleep 10
done
echo "non-running: $N"
kubectl -n longhorn-system get pods | grep -vE 'Running|NAME' | head -5
kubectl -n longhorn-system get volumes.longhorn.io
kubectl -n logging get pod loki-0 --no-headers
# snapshot verification
cat <<'EOF' | kubectl -n logging apply -f -
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: loki-check
spec:
  volumeSnapshotClassName: longhorn
  source:
    persistentVolumeClaimName: storage-loki-0
EOF
for i in $(seq 1 24); do
  RT=$(kubectl -n logging get vs loki-check -o jsonpath='{.status.readyToUse}' 2>/dev/null)
  [ "$RT" = "true" ] && echo "SNAPSHOT READY after $((i*5))s" && break
  sleep 5
done
kubectl -n logging get volumesnapshot
kubectl -n longhorn-system get manager -o jsonpath='{.items[0].spec.image}{"\n"}' 2>/dev/null
kubectl -n longhorn-system get settings.longhorn.io current-instance-manager-image -o jsonpath='{.value}{"\n"}' 2>/dev/null
