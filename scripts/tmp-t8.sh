#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== waiting 240s for longhorn manager/CSI to come up ==="
sleep 240
echo "=== longhorn pods ==="
kubectl -n longhorn-system get pods
echo ""
echo "=== non-running ==="
kubectl -n longhorn-system get pods --field-selector=status.phase!=Running,status.phase!=Succeeded 2>&1 | head -20
echo ""
echo "=== engines/instancemanagers ==="
kubectl -n longhorn-system get instancemanager 2>&1 | head -15
echo "=== engineimage ==="
kubectl -n longhorn-system get engineimage 2>&1
echo ""
echo "=== storageclass ==="
kubectl get sc
echo ""
echo "=== settings ==="
kubectl -n longhorn-system get settings.longhorn.io 2>/dev/null | grep -E 'default-replica-count|default-data-path|NAME' 
kubectl -n longhorn-system get settings.longhorn.io default-replica-count default-data-path -o jsonpath='{range .items[*]}{.metadata.name}={.value}{"\n"}{end}' 2>&1
echo ""
echo "=== nodes in longhorn ==="
kubectl -n longhorn-system get nodes.longhorn.io 2>&1 | head -14
echo ""
echo "=== recent failures ==="
kubectl -n longhorn-system get events --sort-by=.lastTimestamp 2>/dev/null | grep -iE 'fail|error|backoff|unhealthy' | tail -10
