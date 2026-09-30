#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== pods/log CONNECT long-running streams (3 samples, 45s apart) ==="
for i in 1 2 3; do
  v=$(kubectl get --raw='/metrics' 2>/dev/null | grep '^apiserver_longrunning_requests{' | grep 'subresource="log"' | awk '{print $2}')
  echo "  t=$((i*45))s  pods/log streams = ${v:-0}"
  sleep 45
done
echo "=== inflight ==="
kubectl get --raw='/metrics' 2>/dev/null | grep '^apiserver_current_inflight_requests'
echo "=== longhorn not-running now ==="
kubectl -n longhorn-system get pods --no-headers | grep -vcE 'Running|Completed'
echo "=== csi restart totals ==="
kubectl -n longhorn-system get pods -l 'app in (csi-provisioner,csi-attacher,csi-resizer,csi-snapshotter)' --no-headers | awk '{s+=$5} END {print "  total restarts:", s}'