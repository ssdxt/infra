#!/bin/bash
# 备份并安装新的 02-alloy.sh，然后 helm upgrade + 验证
set -u
export KUBECONFIG=/etc/kubernetes/admin.conf
F=/data1/ssdxt/logging/02-alloy.sh
TS=$(date +%m%d-%H%M%S)

echo "=== [1] backup + install new script ==="
cp -a $F $F.bak.$TS && echo "  backup: $F.bak.$TS"
cp /tmp/02-alloy-new.sh $F && chmod +x $F && echo "  installed"
bash -n $F && echo "  bash syntax OK"
echo "  --- head ---"
sed -n '1,12p' $F

echo ""
echo "=== [2] BEFORE: apiserver pods/log long-running streams ==="
for i in 1 2 3; do
  v=$(kubectl get --raw='/metrics' 2>/dev/null | grep '^apiserver_longrunning_requests{' | grep 'subresource="log"' | awk '{print $2}')
  echo "  sample$i pods/log streams = ${v:-0}"
  sleep 5
done
echo "  inflight before:"; kubectl get --raw='/metrics' 2>/dev/null | grep '^apiserver_current_inflight_requests'
echo "  CSI restart totals before:"
kubectl -n longhorn-system get pods -l 'app in (csi-provisioner,csi-attacher,csi-resizer,csi-snapshotter)' --no-headers | awk '{s+=$5} END {print "   ", s}'
echo "  timestamp: $(date +%H:%M:%S)"

echo ""
echo "=== [3] helm upgrade (run the script) ==="
bash $F 2>&1 | tail -14

echo ""
echo "=== [4] wait for DaemonSet 11/11 (max 6min) ==="
last=""
for i in $(seq 1 72); do
  R=$(kubectl -n logging get ds alloy -o jsonpath='{.status.numberReady}' 2>/dev/null)
  D=$(kubectl -n logging get ds alloy -o jsonpath='{.status.desiredNumberScheduled}' 2>/dev/null)
  cur="$R/$D"
  if [ "$cur" != "$last" ]; then echo "  t=$((i*5))s alloy ready=$cur"; last="$cur"; fi
  [ "$R" = "$D" ] && [ -n "$R" ] && [ "$R" != "0" ] && break
  sleep 5
done

echo ""
echo "=== [5] pod state + mounts + env sanity ==="
kubectl -n logging get ds alloy
kubectl -n logging get pods --no-headers | awk '{print $2,$3}' | sort | uniq -c
echo "--- volumes/mounts ---"
kubectl -n logging get ds alloy -o jsonpath='{range .spec.template.spec.volumes[*]}{.name}={.hostPath.path}{"\n"}{end}'
kubectl -n logging get ds alloy -o jsonpath='{range .spec.template.spec.containers[0].volumeMounts[*]}{.name}->{.mountPath} ro={.readOnly}{"\n"}{end}'
echo "--- env ---"
kubectl -n logging get ds alloy -o jsonpath='{.spec.template.spec.containers[0].env}' | head -c 400
echo ""
echo "--- does /var/log/pods exist inside the pod? ---"
P=$(kubectl -n logging get pods -l app.kubernetes.io/name=alloy --no-headers | awk '{print $1}' | head -1)
kubectl -n logging exec $P -c alloy -- sh -c 'echo "NODE_NAME=$NODE_NAME"; ls /var/log/pods | head -3; ls /var/log/pods/*/*/*.log 2>/dev/null | wc -l' 2>&1 | head -8
