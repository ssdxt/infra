#!/bin/bash
set -uo pipefail
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "== state"
kubectl -n logging get volumesnapshot 2>&1 | head -3
kubectl get volumesnapshotcontent 2>&1 | head -3
kubectl -n longhorn-system get snapshots.longhorn.io 2>&1 | head -5
echo "== force clean"
for vs in $(kubectl -n logging get volumesnapshot -o name 2>/dev/null); do
  kubectl -n logging patch $vs --type=merge -p '{"metadata":{"finalizers":null}}' || true
  kubectl -n logging delete $vs --timeout=30s || true
done
for vsc in $(kubectl get volumesnapshotcontent -o name 2>/dev/null); do
  kubectl patch $vsc --type=merge -p '{"metadata":{"finalizers":null}}' || true
  kubectl delete $vsc --timeout=30s || true
done
for s in $(kubectl -n longhorn-system get snapshots.longhorn.io -o name 2>/dev/null); do
  kubectl -n longhorn-system patch $s --type=merge -p '{"metadata":{"finalizers":null}}' || true
  kubectl -n longhorn-system delete $s --timeout=30s || true
done
sleep 3
kubectl -n longhorn-system get snapshots.longhorn.io 2>&1 | head -3
echo "== fresh snapshot"
cat <<'EOF' | kubectl -n logging apply -f -
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: loki-pre-upgrade
spec:
  volumeSnapshotClassName: longhorn
  source:
    persistentVolumeClaimName: storage-loki-0
EOF
for i in $(seq 1 24); do
  RT=$(kubectl -n logging get vs loki-pre-upgrade -o jsonpath='{.status.readyToUse}' 2>/dev/null)
  [ "$RT" = "true" ] && echo "READY after $((i*5))s" && break
  sleep 5
done
kubectl -n logging get volumesnapshot
echo DONE
