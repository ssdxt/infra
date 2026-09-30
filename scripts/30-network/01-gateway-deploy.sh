#!/bin/bash
# 部署 Gateway + HTTPRoute，把监控/存储界面用域名暴露（持久化）
set -e
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=gateway
kubectl create ns $NS --dry-run=client -o yaml | kubectl apply -f -

echo "=== [1/3] 部署 Gateway（kube-vip 会给它分配 LoadBalancer IP）==="
cat <<'YAML' | kubectl apply -f -
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: monitoring-gateway
  namespace: gateway
spec:
  gatewayClassName: cilium
  listeners:
  - name: http
    protocol: HTTP
    port: 80
    allowedRoutes:
      namespaces:
        from: All
YAML

echo "=== [2/3] 在各命名空间建服务别名（Gateway 不能跨命名空间引 Service，用 ReferenceGrant 或同 ns 服务）==="
# 在 gateway 命名空间建 ExternalName 服务指向各后端
for pair in "grafana:prometheus-stack-grafana.monitoring:80" \
            "prometheus:prometheus-stack-kube-prom-prometheus.monitoring:9090" \
            "alertmanager:prometheus-stack-kube-prom-alertmanager.monitoring:9093" \
            "longhorn:longhorn-frontend.longhorn-system:80"; do
  name="${pair%%:*}"; rest="${pair#*:}"; svc="${rest%%:*}"; port="${rest##*:}"
  cat <<YAML | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: $name
  namespace: $NS
spec:
  type: ExternalName
  externalName: $svc
  ports:
  - port: $port
YAML
done

echo "=== [3/3] 部署 HTTPRoute（按域名分流）==="
cat <<'YAML' | kubectl apply -f -
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: monitoring-routes
  namespace: gateway
spec:
  parentRefs:
  - name: monitoring-gateway
  rules:
  - matches: [{path: {type: PathPrefix, value: /}}]
    backendRefs:
    - {name: grafana, port: 80}
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: prometheus-route
  namespace: gateway
spec:
  parentRefs: [{name: monitoring-gateway}]
  hostnames: ["prometheus.wuxing.local"]
  rules:
  - matches: [{path: {type: PathPrefix, value: /}}]
    backendRefs: [{name: prometheus, port: 9090}]
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: alertmanager-route
  namespace: gateway
spec:
  parentRefs: [{name: monitoring-gateway}]
  hostnames: ["alertmanager.wuxing.local"]
  rules:
  - matches: [{path: {type: PathPrefix, value: /}}]
    backendRefs: [{name: alertmanager, port: 9093}]
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: longhorn-route
  namespace: gateway
spec:
  parentRefs: [{name: monitoring-gateway}]
  hostnames: ["longhorn.wuxing.local"]
  rules:
  - matches: [{path: {type: PathPrefix, value: /}}]
    backendRefs: [{name: longhorn, port: 80}]
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: grafana-route
  namespace: gateway
spec:
  parentRefs: [{name: monitoring-gateway}]
  hostnames: ["grafana.wuxing.local"]
  rules:
  - matches: [{path: {type: PathPrefix, value: /}}]
    backendRefs: [{name: grafana, port: 80}]
YAML

echo ""
echo "=== 等 30 秒看 LB IP ==="
sleep 30
kubectl get gateway -n $NS
GWIP=$(kubectl get gateway monitoring-gateway -n $NS -o jsonpath='{.status.addresses[0].value}' 2>/dev/null)
echo ""
echo "Gateway IP: ${GWIP:-未分配（检查 kube-vip svc_enable 是否为 true）}"
echo ""
echo "在访问者机器上加 hosts:"
echo "  ${GWIP:-<IP>}  grafana.wuxing.local prometheus.wuxing.local alertmanager.wuxing.local longhorn.wuxing.local"
echo ""
echo "注: HTTPS 需要给 Gateway 加 443 listener + cert-manager 证书，见 README"
