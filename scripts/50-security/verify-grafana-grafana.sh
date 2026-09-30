#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
GRAF=$(kubectl -n monitoring get pod -l app.kubernetes.io/name=grafana -o name | head -1)
echo "== sidecar 日志"
kubectl -n monitoring logs $GRAF grafana-sc-dashboard --tail=10 2>/dev/null | tail -4
echo "== grafana API 搜 Tetragon 看板"
PW=$(kubectl -n monitoring get secret prometheus-stack-grafana -o jsonpath='{.data.admin-password}' | base64 -d)
B64=$(printf "admin:%s" "$PW" | base64 -w0)
kubectl -n monitoring exec $GRAF -c grafana -- wget -qO- --header="Authorization: Basic $B64" 'http://localhost:3000/api/search?query=Tetragon' | head -c 400
echo
echo "== prometheus targets 中 tetragon"
PW2=$(kubectl -n monitoring get secret prometheus-stack-grafana -o jsonpath='{.data.admin-password}' | base64 -d)
kubectl -n monitoring get servicemonitor -l release=prometheus-stack 2>/dev/null | grep -i tetragon
kubectl -n monitoring exec $GRAF -c grafana -- wget -qO- --header="Authorization: Basic $B64" 'http://localhost:3000/api/datasources' | grep -o '"name":"[^"]*"' | head -3
PROM=$(kubectl -n monitoring get pod -l app.kubernetes.io/name=prometheus -o name | head -1)
kubectl -n monitoring exec $PROM -- wget -qO- 'http://localhost:9090/api/v1/targets?state=active' 2>/dev/null | grep -o 'tetragon[^"]*' | sort -u | head -5
