#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== longhorn backend service ==="
kubectl -n longhorn-system get svc longhorn-frontend -o wide 2>&1
kubectl -n longhorn-system get svc longhorn-frontend -o jsonpath='type={.spec.type} ports={.spec.ports}'; echo
echo
echo "=== create ReferenceGrant in longhorn-system ==="
cat > /tmp/gwfix-bak/refgrant-longhorn.yaml <<'YAML'
apiVersion: gateway.networking.k8s.io/v1beta1
kind: ReferenceGrant
metadata:
  name: allow-gateway-httproutes
  namespace: longhorn-system
spec:
  from:
  - group: gateway.networking.k8s.io
    kind: HTTPRoute
    namespace: gateway
  to:
  - group: ""
    kind: Service
YAML
kubectl apply -f /tmp/gwfix-bak/refgrant-longhorn.yaml
echo
echo "=== repoint longhorn-route to the real Service ==="
kubectl -n gateway patch httproute longhorn-route --type merge -p '{"spec":{"rules":[{"matches":[{"path":{"type":"PathPrefix","value":"/"}}],"backendRefs":[{"group":"","kind":"Service","name":"longhorn-frontend","namespace":"longhorn-system","port":80,"weight":1}]}]}}'
echo
echo "=== wait 40s ==="
sleep 40
kubectl get httproute -A
kubectl get httproute -A -o jsonpath='{range .items[*]}{.metadata.name}{"  "}{range .status.parents[*].conditions[*]}{.type}={.status}/{.reason} {end}{"\n"}{end}'
echo
IP=$(kubectl get gateway -n gateway monitoring-gateway -o jsonpath='{.status.addresses[0].value}')
echo "=== FULL curl matrix via $IP ==="
for hp in "grafana.wuxing.local:/login" "grafana.wuxing.local:/" "prometheus.wuxing.local:/graph" "alertmanager.wuxing.local:/" "longhorn.wuxing.local:/"; do
  h=${hp%%:*}; p=${hp#*:}
  printf '  %-42s -> %s\n' "$h$p" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 -H "Host: $h" http://$IP$p)"
done
echo
echo "=== bodies (proof) ==="
curl -s --max-time 10 -H 'Host: grafana.wuxing.local' http://$IP/login | grep -oE '<title>[^<]*</title>' | head -1
curl -s --max-time 10 -H 'Host: prometheus.wuxing.local' http://$IP/graph | grep -oE '<title>[^<]*</title>' | head -1
curl -s --max-time 10 -H 'Host: alertmanager.wuxing.local' http://$IP/ | grep -oE '<title>[^<]*</title>' | head -1
curl -s --max-time 10 -H 'Host: longhorn.wuxing.local' http://$IP/ | grep -oE '<title>[^<]*</title>' | head -1
echo
echo "=== gateway final ==="
kubectl get gateway -n gateway
echo "=== referencegrants ==="
kubectl get referencegrant -A
