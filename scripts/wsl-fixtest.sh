#!/bin/bash
set -u
C=/tmp/dsh-charts
H=harbor.wuxing.local
mkdir -p /tmp/fixtest && cd /tmp/fixtest

render() {  # $1=chart $2=project $3=extracustom
  local chart=$1 proj=$2 custom=$3
  python3 /mnt/c/Users/CC/Desktop/dsh/fix-chart-images.py $chart $proj $H /tmp/fixtest/$proj-harbor.yaml
  helm template t $chart -n ns -f /tmp/fixtest/$proj-harbor.yaml ${custom:+-f $custom} > /tmp/fixtest/$proj-render.yaml 2>/tmp/fixtest/$proj.err \
    || { echo "TEMPLATE FAILED for $proj"; cat /tmp/fixtest/$proj.err; }
  echo "--- [$proj] rendered images (unique) ---"
  grep -E '^[[:space:]]+-?[[:space:]]*image:' /tmp/fixtest/$proj-render.yaml | sed 's/.*image: *//' | tr -d '"' | sort -u
}

echo "############ LONGHORN with fix script ############"
cat > /tmp/fixtest/lh-custom.yaml <<'YAML'
defaultSettings:
  defaultReplicaCount: 2
  defaultDataPath: /data1/longhorn
  concurrentReplicaRebuildPerNodeLimit: 1
persistence:
  defaultClass: true
  defaultClassReplicaCount: 2
YAML
render $C/longhorn-1.7.2.tgz longhorn /tmp/fixtest/lh-custom.yaml
echo "--- longhorn global.cattle in fixed values ---"
grep -n -A5 'cattle' /tmp/fixtest/longhorn-harbor.yaml | head -20

echo ""
echo "############ LOKI with fix script ############"
render $C/loki-6.24.0.tgz logging /tmp/loki-custom.yaml
echo "--- loki fixed values: any registry/repository pairs ---"
grep -n -B3 -A2 'repository: harbor' /tmp/fixtest/logging-harbor.yaml | head -40

echo ""
echo "############ ALLOY with fix script ############"
render $C/alloy-0.12.0.tgz logging /tmp/alloy-custom.yaml
echo "--- alloy fixed values image block ---"
sed -n '/^image:/,/^rbac:/p' /tmp/fixtest/alloy-harbor.yaml 2>/dev/null | head -20
ls -la /tmp/fixtest/
