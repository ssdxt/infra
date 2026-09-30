#!/bin/bash
set -u
C=/tmp/dsh-charts
echo "############ ALLOY: image + configMap/configReloader keys ############"
helm show values $C/alloy-0.12.0.tgz > /tmp/alloy-values.yaml
grep -n -E '^image:|  repository:|  tag:|^configMap:|^controller:|^  type:|^configReloader:|^  enabled:|^  create:' /tmp/alloy-values.yaml | head -40
echo "--- alloy image block ---"
sed -n '/^image:/,/^[a-z]/p' /tmp/alloy-values.yaml | head -20
echo "--- alloy configMap block ---"
sed -n '/^configMap:/,/^[a-z]/p' /tmp/alloy-values.yaml | head -20
echo "--- configReloader block ---"
sed -n '/^configReloader:/,/^[a-z]/p' /tmp/alloy-values.yaml | head -20

echo ""
echo "############ LONGHORN: default images ############"
helm show values $C/longhorn-1.7.2.tgz > /tmp/lh-values.yaml
grep -n -E 'repository:|tag:|registry:' /tmp/lh-values.yaml | head -60
echo "--- longhorn defaultSettings keys of interest ---"
grep -n -E 'defaultReplicaCount|defaultDataPath|defaultClass|concurrentReplicaRebuild' /tmp/lh-values.yaml | head -20

echo ""
echo "############ LOKI: images + service ports ############"
helm show values $C/loki-6.24.0.tgz > /tmp/loki-values.yaml
grep -n -E 'repository:|tag:|registry:' /tmp/loki-values.yaml | head -60
echo "--- loki deploymentMode/singleBinary keys ---"
grep -n -E 'deploymentMode|^singleBinary:|^  replicas:|^  persistence:' /tmp/loki-values.yaml | head -20
echo "--- loki chart templates: services ---"
helm template loki $C/loki-6.24.0.tgz -n logging --set deploymentMode=SingleBinary --set backend.replicas=0 --set read.replicas=0 --set write.replicas=0 2>/dev/null | grep -E '^kind: Service|^  name: ' | head -40
