#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== longhorn pods (non-running only if any) ==="
kubectl -n longhorn-system get pods 2>&1 | grep -vE 'Running|Completed' | head -25
echo "--- total ---"
kubectl -n longhorn-system get pods --no-headers 2>&1 | wc -l
kubectl -n longhorn-system get pods --no-headers 2>&1 | awk '{print $3}' | sort | uniq -c
echo ""
echo "=== volume/engine state ==="
kubectl -n longhorn-system get instancemanager 2>&1 | head -12
echo ""
echo "=== pvc test: create 1Gi on longhorn ==="
kubectl create ns stotest 2>&1 | tail -1
cat <<'Y' | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata: {name: t, namespace: stotest}
spec:
  accessModes: ["ReadWriteOnce"]
  storageClassName: longhorn
  resources: {requests: {storage: 1Gi}}
Y
echo "--- waiting up to 120s for Bound ---"
for i in $(seq 1 24); do
  ph=$(kubectl -n stotest get pvc t -o jsonpath='{.status.phase}' 2>/dev/null)
  echo "  t=${i}0s phase=$ph"
  [ "$ph" = "Bound" ] && break
  sleep 5
done
echo ""
kubectl -n stotest get pvc t
echo ""
kubectl -n longhorn-system get volumes.longhorn.io 2>&1 | head -8
echo ""
PH=$(kubectl -n stotest get pvc t -o jsonpath='{.status.phase}' 2>/dev/null)
if [ "$PH" = "Bound" ]; then
  echo "=== cleanup (PVC was Bound) ==="
  kubectl -n stotest delete pvc t --wait=false 2>&1
  kubectl delete ns stotest --wait=false 2>&1
else
  echo "=== NOT Bound (phase=$PH) - keeping stotest ns for diagnosis ==="
  kubectl -n stotest describe pvc t 2>&1 | tail -15
  kubectl -n longhorn-system get events --sort-by=.lastTimestamp 2>/dev/null | tail -10
fi
