#!/bin/bash
set -uo pipefail
export KUBECONFIG=/etc/kubernetes/admin.conf
kubectl -n longhorn-system get deploy csi-snapshotter -o yaml | grep -B2 -A12 'volumes:'
echo "=== longhorn snapshot CRD types present"
kubectl -n longhorn-system get snapshots.longhorn.io 2>&1 | head -3
kubectl get crd | grep -E 'snapshot|backup'
echo "=== csi plugin socket dir on node"
sshpass not needed; check hostpath via plugin pod:
P=$(kubectl -n longhorn-system get pods -o name | grep longhorn-csi-plugin | head -1)
kubectl -n longhorn-system get pod $P -o jsonpath='{.spec.volumes}' | python3 -c "import json,sys; [print(v['name'], v.get('hostPath',{}).get('path') or v.get('emptyDir') or v.get('configMap') and 'cm') for v in json.load(sys.stdin)]"
