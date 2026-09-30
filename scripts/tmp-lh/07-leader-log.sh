#!/bin/bash
set -uo pipefail
export KUBECONFIG=/etc/kubernetes/admin.conf
kubectl -n longhorn-system logs csi-snapshotter-8548b8b9f7-fntch 2>&1 | grep -vE 'Probing|main.go:108|main.go:188' 
echo "=== vs with wide"
kubectl -n logging get volumesnapshot -o wide
kubectl -n logging get volumesnapshotcontent 2>&1 | head -3
