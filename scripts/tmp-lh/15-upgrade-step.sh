#!/bin/bash
# usage: upgrade-step.sh <version>
set -uo pipefail
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=longhorn-system
V=$1
CHART=/data1/ssdxt/charts/longhorn-upgrade/longhorn-$V.tgz
VALS=/data1/ssdxt/charts/longhorn-upgrade/values-harbor-$V.yaml
CUSTOM=/data1/ssdxt/charts/longhorn-upgrade/custom-values.yaml
BK=/data1/ssdxt/storage/backup/upgrade-step-$V-$(date +%H%M)
echo "== pre-backup to $BK"
mkdir -p "$BK"
kubectl -n $NS get volumes.longhorn.io,settings.longhorn.io,nodes.longhorn.io,deployments -o yaml > "$BK/resources.yaml"
kubectl -n $NS get secret longhorn-webhook-ca longhorn-webhook-tls -o yaml > "$BK/webhook-secrets.yaml"
echo "== helm upgrade to $V"
helm upgrade longhorn "$CHART" -n $NS -f "$VALS" -f "$CUSTOM" --timeout 15m 2>&1 | tail -15
echo "== wait rollout"
kubectl -n $NS rollout status ds/longhorn-manager --timeout=300s
kubectl -n $NS rollout status ds/longhorn-csi-plugin --timeout=300s
kubectl -n $NS rollout status deploy/longhorn-ui --timeout=180s
sleep 30
echo "== pods"
kubectl -n $NS get pods | awk '$2!="1/1" && $2!="2/2" && $3!="Running" || NR==1' | head -20
kubectl -n $NS get pods --no-headers | grep -vE 'Running|Completed' | wc -l
echo "== volume"
kubectl -n $NS get volumes.longhorn.io
echo "== loki"
kubectl -n logging get pod loki-0 | tail -1
kubectl -n logging get pvc storage-loki-0
echo "== helm"
helm -n $NS list | grep longhorn
echo STEP-DONE
