#!/bin/bash
# control-01: sync mirror.sh list (ASCII only) and run longhorn install
set -u
R=/data1/ssdxt
TS=$(date +%m%d-%H%M%S)

echo "=== [1] sync images/mirror.sh (add k8s-sidecar) ==="
if grep -q 'k8s-sidecar' $R/images/mirror.sh; then
  echo "  already present, skip"
else
  cp -a $R/images/mirror.sh $R/images/mirror.sh.bak.$TS
  echo "  backup: $R/images/mirror.sh.bak.$TS"
  python3 - <<'PY'
p = '/data1/ssdxt/images/mirror.sh'
s = open(p).read()
new = 'kiwigrid/k8s-sidecar:1.28.0|logging/k8s-sidecar:1.28.0\n'
anchor = 'grafana/alloy:v1.7.0|logging/alloy:v1.7.0\n'
if anchor in s:
    open(p, 'w').write(s.replace(anchor, anchor + new, 1))
    print('  inserted k8s-sidecar line')
else:
    print('  ANCHOR NOT FOUND - not modified')
PY
fi
echo "  --- LOGGING list now ---"
sed -n '/^LIST_LOGGING=/,/^.LIST_LOGGING_END/p' $R/images/mirror.sh | head -12
grep -n 'sidecar' $R/images/mirror.sh

echo ""
echo "=== [2] pre-check open-iscsi on all 11 nodes ==="
for ip in 10.100.10.10 10.100.10.14 10.100.10.19 10.100.10.33 10.100.10.34 10.100.10.39 10.100.10.41 10.100.10.44 10.100.10.45 10.100.10.46 10.100.10.47; do
  st=$(ssh -o BatchMode=yes -o ConnectTimeout=6 root@$ip 'dpkg -l 2>/dev/null | grep -c "^ii  open-iscsi"; systemctl is-active iscsid 2>/dev/null' 2>&1 | tr "\n" " ")
  echo "  $ip -> $st"
done

echo ""
echo "=== [3] run longhorn install script ==="
bash $R/storage/03-longhorn-install.sh 2>&1
echo "EXIT=$?"
