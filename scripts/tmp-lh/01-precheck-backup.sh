#!/bin/bash
set -uo pipefail
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=longhorn-system
BK=/data1/ssdxt/storage/backup/upgrade-$(date +%Y%m%d-%H%M)
mkdir -p "$BK"

echo "=== 1. volume replicas health"
V=$(kubectl -n $NS get volumes.longhorn.io -o jsonpath='{.items[0].metadata.name}')
kubectl -n $NS get volumes.longhorn.io
kubectl -n $NS get volumeattachments.longhorn.io 2>/dev/null | head -5
kubectl -n $NS get replicas.longhorn.io -o wide | grep -v NAME | awk '{print $1,$3,$4,$6}' 
kubectl -n $NS get volume pvc-c39f2fee-b8f9-4175-a0c7-1031ca24656b -o jsonpath='robustness={.status.robustness} replicas={.spec.numberOfReplicas}{"\n"}'

echo "=== 2. webhook secret annotations"
kubectl -n $NS get secret longhorn-webhook-ca longhorn-webhook-tls -o jsonpath='{range .items[*]}{.metadata.name}{" static="}{.metadata.annotations.listener\.cattle\.io/static}{" rv="}{.metadata.resourceVersion}{"\n"}{end}'

echo "=== 3. export resources to $BK"
kubectl -n $NS get volumes.longhorn.io -o yaml > "$BK/volumes.yaml"
kubectl -n $NS get settings.longhorn.io -o yaml > "$BK/settings.yaml"
kubectl -n $NS get nodes.longhorn.io -o yaml > "$BK/nodes.yaml"
kubectl -n $NS get deployments -o yaml > "$BK/deployments.yaml"
kubectl -n $NS get secret longhorn-webhook-ca longhorn-webhook-tls -o yaml > "$BK/webhook-secrets.yaml"
helm -n $NS get values longhorn -a > "$BK/helm-values-1.7.2.yaml"
helm list -n $NS > "$BK/helm-list.txt"
ls -la "$BK"

echo "=== 4. VolumeSnapshotClass (create if missing)"
if ! kubectl get volumesnapshotclass longhorn >/dev/null 2>&1; then
cat <<EOF | kubectl apply -f -
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshotClass
metadata:
  name: longhorn
driver: driver.longhorn.io
deletionPolicy: Delete
EOF
fi
kubectl get volumesnapshotclass

echo "=== 5. snapshot of loki PVC"
PVC=$(kubectl -n logging get pvc | grep storage-loki-0 | awk '{print $1}' | head -1)
echo "PVC=$PVC"
cat <<EOF | kubectl -n logging apply -f -
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: loki-pre-upgrade-$(date +%Y%m%d)
spec:
  volumeSnapshotClassName: longhorn
  source:
    persistentVolumeClaimName: $PVC
EOF
echo "snapshot created, waiting for READYTOUSE..."
for i in $(seq 1 24); do
  RT=$(kubectl -n logging get vs loki-pre-upgrade-$(date +%Y%m%d) -o jsonpath='{.status.readyToUse}' 2>/dev/null)
  [ "$RT" = "true" ] && break
  sleep 5
done
kubectl -n logging get volumesnapshot
echo "=== 6. loki-0 status"
kubectl -n logging get pod loki-0
echo DONE
