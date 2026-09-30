#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== waiting 120s for loki-0 ==="
sleep 120
kubectl -n logging get pods -o wide
kubectl -n logging get pvc
echo "=== loki-0 containers ==="
kubectl -n logging get pod loki-0 -o jsonpath='{range .status.containerStatuses[*]}{.name}: ready={.ready} restarts={.restartCount} image={.image}{"\n"}{end}' 2>&1
echo "=== recent logging events ==="
kubectl -n logging get events --sort-by=.lastTimestamp 2>&1 | tail -12
echo "=== csi-snapshotter now ==="
kubectl -n longhorn-system get pods -l app=csi-snapshotter 2>&1