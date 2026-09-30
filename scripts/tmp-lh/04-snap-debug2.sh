#!/bin/bash
set -uo pipefail
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== new snapshotter pods"
kubectl -n longhorn-system get pods -o wide | grep csi-snapshotter
echo "=== deploy spec (args/env)"
kubectl -n longhorn-system get deploy csi-snapshotter -o yaml | grep -A30 'containers:'
echo "=== logs of each new pod"
for p in $(kubectl -n longhorn-system get pods -o name | grep csi-snapshotter); do
  echo "--- $p"; kubectl -n longhorn-system logs $p --tail=12 2>&1 | grep -vE 'reflect|Caches'
done
echo "=== leader lease now"
kubectl -n longhorn-system get lease external-snapshotter-leader-driver-longhorn-io -o jsonpath='{.spec.holderIdentity} {.spec.renewTime}{"\n"}'
echo "=== csi plugin CreateSnapshot"
for p in $(kubectl -n longhorn-system get pods -o name | grep longhorn-csi-plugin | head -3); do
  kubectl -n longhorn-system logs $p -c longhorn-csi-plugin 2>&1 | grep -i snapshot | tail -5
done
