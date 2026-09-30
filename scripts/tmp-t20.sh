#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf

echo "=== [1] Grafana sidecar datasource config ==="
kubectl -n monitoring get deploy prometheus-stack-grafana -o jsonpath='{.spec.template.spec.containers[*].name}' 2>&1
echo ""
kubectl -n monitoring get deploy prometheus-stack-grafana -o yaml 2>/dev/null | grep -E 'sidecar|label:|labelValue|resource:|image:' | head -20
echo "--- existing datasource configmaps in monitoring ---"
kubectl -n monitoring get cm --show-labels 2>&1 | grep -i -E 'datasource|grafana' | head -10

echo ""
echo "=== [2] wait 130s for Alloy to push logs into Loki ==="
sleep 130

echo "=== [3] Loki labels API ==="
kubectl -n logging exec loki-0 -c loki -- wget -qO- 'http://localhost:3100/loki/api/v1/labels' 2>&1 | head -c 600
echo ""
echo "=== [4] Loki label 'namespace' values ==="
kubectl -n logging exec loki-0 -c loki -- wget -qO- 'http://localhost:3100/loki/api/v1/label/namespace/values' 2>&1 | head -c 600
echo ""
echo "=== [5] LogQL instant query: count_over_time by namespace ==="
kubectl -n logging exec loki-0 -c loki -- wget -qO- 'http://localhost:3100/loki/api/v1/query?query=sum(count_over_time(%7Bnamespace%3D~%22.%2B%22%7D%5B10m%5D))by(namespace)' 2>&1 | head -c 1000
echo ""
echo "=== [6] real log lines from kube-system ==="
kubectl -n logging exec loki-0 -c loki -- wget -qO- 'http://localhost:3100/loki/api/v1/query_range?query=%7Bnamespace%3D%22kube-system%22%7D&limit=2' 2>&1 | head -c 1200
echo ""
echo "=== [7] alloy logs: pushing ok? ==="
kubectl -n logging logs alloy-djl8p --tail=15 2>&1 | tail -15
