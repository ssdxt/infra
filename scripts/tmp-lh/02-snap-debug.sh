#!/bin/bash
set -uo pipefail
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== describe vs"
kubectl -n logging describe volumesnapshot loki-pre-upgrade-20260930 | tail -25
echo "=== snapshotter pods"
kubectl -n longhorn-system get pods -l app=csi-snapshotter 2>/dev/null
kubectl -n longhorn-system get deploy csi-snapshotter -o jsonpath='{.spec.selector.matchLabels}{"\n"}'
echo "=== recent snapshotter log"
P=$(kubectl -n longhorn-system get pods -o name | grep csi-snapshotter | head -1)
kubectl -n longhorn-system logs $P --tail=25 2>&1
echo "=== manager log snapshot mentions"
kubectl -n longhorn-system get pods | grep manager | grep -v instance | grep -v backing | grep -v share
