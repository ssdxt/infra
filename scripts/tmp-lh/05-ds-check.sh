#!/bin/bash
set -uo pipefail
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== csi plugin DS containers"
kubectl -n longhorn-system get ds longhorn-csi-plugin -o jsonpath='{range .spec.template.spec.containers[*]}{.name}{" "}{.image}{"\n"}{end}'
echo "=== snapshotter sidecar logs in plugin pod"
P=$(kubectl -n longhorn-system get pods -o name | grep longhorn-csi-plugin | head -1)
echo $P
kubectl -n longhorn-system logs $P -c csi-snapshotter --tail=15 2>&1
echo "=== check vs again"
kubectl -n logging get volumesnapshot
