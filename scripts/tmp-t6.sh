#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== iscsid active on all nodes (post-install) ==="
for ip in 10.100.10.10 10.100.10.14 10.100.10.19 10.100.10.33 10.100.10.34 10.100.10.39 10.100.10.41 10.100.10.44 10.100.10.45 10.100.10.46 10.100.10.47; do
  printf "  %s -> %s\n" "$ip" "$(ssh -o BatchMode=yes -o ConnectTimeout=6 root@$ip 'systemctl is-active iscsid' 2>&1)"
done

echo ""
echo "=== waiting 90s for longhorn pods to initialize ==="
sleep 90

echo "=== longhorn pods ==="
kubectl -n longhorn-system get pods -o wide
echo ""
echo "=== longhorn svc ==="
kubectl -n longhorn-system get svc
echo ""
echo "=== storageclass ==="
kubectl get sc
echo ""
echo "=== pending / non-running pods ==="
kubectl -n longhorn-system get pods --field-selector=status.phase!=Running,status.phase!=Succeeded 2>&1 | head -20
echo ""
echo "=== image pull problems (if any) ==="
kubectl -n longhorn-system get events --sort-by=.lastTimestamp 2>/dev/null | grep -iE 'failed|pull|backoff' | tail -15
echo ""
echo "=== longhorn settings check ==="
kubectl -n longhorn-system get settings.longhorn.io default-replica-count default-data-path -o jsonpath='{range .items[*]}{.metadata.name}={.value}{"\n"}{end}'
echo ""
echo "=== helm release ==="
helm -n longhorn-system list
