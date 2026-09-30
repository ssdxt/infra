#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf

echo "=== [A] wait for alloy DaemonSet ready (max 10min) ==="
for i in $(seq 1 60); do
  R=$(kubectl -n logging get ds alloy -o jsonpath='{.status.numberReady}' 2>/dev/null)
  D=$(kubectl -n logging get ds alloy -o jsonpath='{.status.desiredNumberScheduled}' 2>/dev/null)
  echo "  t=${i}0s alloy ready=$R/$D"
  [ "$R" = "$D" ] && [ -n "$R" ] && break
  sleep 10
done

echo ""
echo "=== [B] logging pods ==="
kubectl -n logging get pods -o wide

echo ""
echo "=== [C] logging svc ==="
kubectl -n logging get svc

echo ""
echo "=== [D] Loki labels API ==="
kubectl -n logging exec loki-0 -c loki -- wget -qO- 'http://localhost:3100/loki/api/v1/labels' 2>&1 | head -c 500
echo ""
echo "=== [D2] Loki ready ==="
kubectl -n logging exec loki-0 -c loki -- wget -qO- 'http://localhost:3100/ready' 2>&1 | head -c 200

echo ""
echo "=== [E] LogQL query: log volume by namespace (last 1h) ==="
kubectl -n logging exec loki-0 -c loki -- wget -qO- 'http://localhost:3100/loki/api/v1/query?query=sum(count_over_time({namespace=~".+"}[1h]))by(namespace)&time='$(date +%s) 2>&1 | head -c 800

echo ""
echo "=== [F] LogQL query_range sample: real log lines ==="
kubectl -n logging exec loki-0 -c loki -- wget -qO- 'http://localhost:3100/loki/api/v1/query_range?query=%7Bnamespace%3D%22logging%22%7D&limit=3' 2>&1 | head -c 1200

echo ""
echo "=== [G] alloy logs: errors? ==="
for p in $(kubectl -n logging get pods -l app.kubernetes.io/name=alloy --no-headers 2>/dev/null | awk '{print $1}' | head -2); do
  echo "--- $p ---"
  kubectl -n logging logs $p --tail=12 2>&1 | tail -12
done

echo ""
echo "=== [H] longhorn full sweep ==="
kubectl -n longhorn-system get pods --no-headers | awk '{print $2, $3}' | sort | uniq -c
echo "--- any not Running/Succeeded ---"
kubectl -n longhorn-system get pods --no-headers | grep -vE 'Running|Completed' || echo "  none"
echo "--- SC ---"
kubectl get sc
echo "--- longhorn-frontend svc ---"
kubectl -n longhorn-system get svc longhorn-frontend
