#!/bin/bash
set -u
C=/tmp/dsh-charts
H=harbor.wuxing.local
FIX=/mnt/c/Users/CC/Desktop/dsh/fix-chart-images-v2.py

echo "############ LONGHORN (v2 tool) ############"
python3 $FIX $C/longhorn-1.7.2.tgz longhorn $H /tmp/v2-lh.yaml
helm template t $C/longhorn-1.7.2.tgz -n longhorn-system -f /tmp/v2-lh.yaml -f /tmp/fixtest/lh-custom.yaml 2>/dev/null \
 | grep -E '^[[:space:]]+-?[[:space:]]*image:' | sed 's/.*image: *//' | tr -d '"' | sort -u

echo "############ LOKI (v2 tool) ############"
python3 $FIX $C/loki-6.24.0.tgz logging $H /tmp/v2-loki.yaml
helm template t $C/loki-6.24.0.tgz -n logging -f /tmp/v2-loki.yaml -f /tmp/loki-custom.yaml 2>/dev/null > /tmp/v2-loki-render.yaml
grep -E '^[[:space:]]+-?[[:space:]]*image:' /tmp/v2-loki-render.yaml | sed 's/.*image: *//' | tr -d '"' | sort -u
echo "--- where is k8s-sidecar used? ---"
grep -n -B25 'k8s-sidecar' /tmp/v2-loki-render.yaml | grep -E 'kind: |  name: |containers:|  - name:|image: ' | tail -12

echo "############ ALLOY (v2 tool) ############"
python3 $FIX $C/alloy-0.12.0.tgz logging $H /tmp/v2-alloy.yaml
helm template t $C/alloy-0.12.0.tgz -n logging -f /tmp/v2-alloy.yaml -f /tmp/alloy-custom.yaml 2>/dev/null \
 | grep -E '^[[:space:]]+-?[[:space:]]*image:' | sed 's/.*image: *//' | tr -d '"' | sort -u

echo "############ METRICS-SERVER image (hardcoded in script) ############"
grep -n 'IMG=' /mnt/c/Users/CC/Desktop/dsh/tmp-t3.sh 2>/dev/null
echo "############ mirror status ############"
tail -3 /tmp/mirror-run.log
pgrep -af mirror.sh || echo MIRROR_STOPPED
