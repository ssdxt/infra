#!/bin/bash
set -u
C=/tmp/dsh-charts
H=harbor.wuxing.local
echo "############ where is k8s-sidecar used in loki render? ############"
grep -n -B12 'k8s-sidecar' /tmp/fixtest/logging-render.yaml | head -40
echo ""
echo "############ test FIXED fix-chart-images.py (registry -> '') ############"
sed "s|node\['registry'\] = harbor|node['registry'] = ''|" /mnt/c/Users/CC/Desktop/dsh/fix-chart-images.py > /tmp/fix-fixed.py
grep -n "registry'\] =" /tmp/fix-fixed.py

echo "--- LOKI fixed render images ---"
python3 /tmp/fix-fixed.py $C/loki-6.24.0.tgz logging $H /tmp/loki-harbor-fixed.yaml
helm template t $C/loki-6.24.0.tgz -n logging -f /tmp/loki-harbor-fixed.yaml -f /tmp/loki-custom.yaml 2>/dev/null | grep -E '^[[:space:]]+-?[[:space:]]*image:' | sed 's/.*image: *//' | tr -d '"' | sort -u

echo "--- ALLOY fixed render images ---"
python3 /tmp/fix-fixed.py $C/alloy-0.12.0.tgz logging $H /tmp/alloy-harbor-fixed.yaml
helm template t $C/alloy-0.12.0.tgz -n logging -f /tmp/alloy-harbor-fixed.yaml -f /tmp/alloy-custom.yaml 2>/dev/null | grep -E '^[[:space:]]+-?[[:space:]]*image:' | sed 's/.*image: *//' | tr -d '"' | sort -u
echo "--- alloy global.image ---"
grep -n -A4 '^global:' /tmp/alloy-harbor-fixed.yaml | head -12

echo "--- LONGHORN fixed render images (regression check) ---"
python3 /tmp/fix-fixed.py $C/longhorn-1.7.2.tgz longhorn $H /tmp/lh-harbor-fixed.yaml
helm template t $C/longhorn-1.7.2.tgz -n longhorn-system -f /tmp/lh-harbor-fixed.yaml -f /tmp/fixtest/lh-custom.yaml 2>/dev/null | grep -E '^[[:space:]]+-?[[:space:]]*image:' | sed 's/.*image: *//' | tr -d '"' | sort -u

echo ""
echo "############ mirror log tail ############"
tail -5 /tmp/mirror-run.log
pgrep -af mirror.sh || echo MIRROR_STOPPED
