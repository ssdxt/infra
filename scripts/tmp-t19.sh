#!/bin/bash
# Fix Alloy config: discovery.relabel needs explicit `targets`
set -u
export KUBECONFIG=/etc/kubernetes/admin.conf
F=/data1/ssdxt/logging/02-alloy.sh
TS=$(date +%m%d-%H%M%S)

echo "=== [1] backup $F ==="
cp -a $F $F.bak.$TS && echo "  backup: $F.bak.$TS"

echo ""
echo "=== [2] insert 'targets' line into discovery.relabel block ==="
python3 - <<'PY'
p = '/data1/ssdxt/logging/02-alloy.sh'
s = open(p, encoding='utf-8').read()
anchor = '      discovery.relabel "pods" {\n'
add = '        targets    = discovery.kubernetes.pods.targets\n'
if 'discovery.kubernetes.pods.targets' in s:
    print('  already present, skip')
elif anchor in s:
    open(p, 'w', encoding='utf-8').write(s.replace(anchor, anchor + add, 1))
    print('  inserted targets line')
else:
    print('  ANCHOR NOT FOUND - aborting')
PY

echo ""
echo "=== [3] resulting config block in script ==="
sed -n '/alloy:/,/configReloader:/p' $F

echo ""
echo "=== [4] re-run alloy install ==="
bash $F 2>&1 | tail -12

echo ""
echo "=== [5] wait for DaemonSet ready (max 8min) ==="
last=""
for i in $(seq 1 96); do
  R=$(kubectl -n logging get ds alloy -o jsonpath='{.status.numberReady}' 2>/dev/null)
  D=$(kubectl -n logging get ds alloy -o jsonpath='{.status.desiredNumberScheduled}' 2>/dev/null)
  cur="$R/$D"
  if [ "$cur" != "$last" ]; then echo "  t=$((i*5))s alloy ready=$cur"; last="$cur"; fi
  [ "$R" = "$D" ] && [ -n "$R" ] && [ "$R" != "0" ] && break
  sleep 5
done

echo ""
echo "=== [6] daemonset + pods ==="
kubectl -n logging get ds alloy
kubectl -n logging get pods -o wide | head -20
echo "--- pod status counts ---"
kubectl -n logging get pods --no-headers | awk '{print $2, $3}' | sort | uniq -c
