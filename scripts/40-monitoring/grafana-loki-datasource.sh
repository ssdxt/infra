#!/bin/bash
# 把 Loki 加成 Grafana 数据源（kube-prometheus-stack 的 sidecar 会自动加载带 grafana_datasource=1 标签的 ConfigMap）
set -u
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=monitoring
LOKI_URL=http://loki.logging.svc.cluster.local:3100

echo "=== [1] ConfigMap loki-datasource ==="
kubectl -n $NS create configmap loki-datasource --from-literal=loki-ds.yaml="apiVersion: 1
datasources:
- name: Loki
  type: loki
  url: $LOKI_URL
  access: proxy
  isDefault: false" --dry-run=client -o yaml | kubectl apply -f -

echo "=== [2] label grafana_datasource=1 ==="
kubectl -n $NS label configmap loki-datasource grafana_datasource=1 --overwrite

echo "=== [3] restart grafana ==="
kubectl -n $NS rollout restart deploy/prometheus-stack-grafana
kubectl -n $NS rollout status deploy/prometheus-stack-grafana --timeout=300s

echo ""
echo "=== [4] verify via Grafana API ==="
PW=$(kubectl -n $NS get secret prometheus-stack-grafana -o jsonpath='{.data.admin-password}' | base64 -d)
echo "  (admin password retrieved, length ${#PW})"
kubectl -n $NS exec deploy/prometheus-stack-grafana -c grafana -- sh -c "wget -qO- 'http://admin:$PW@localhost:3000/api/datasources' 2>/dev/null || curl -s 'http://admin:$PW@localhost:3000/api/datasources'" 2>&1 | head -c 1500
echo ""
echo "=== [5] sidecar log (datasource loader) ==="
kubectl -n $NS logs deploy/prometheus-stack-grafana -c grafana-sc-datasources --tail=15 2>&1
