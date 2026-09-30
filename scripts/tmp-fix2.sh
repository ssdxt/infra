#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
set -u
echo "########## STEP 1: create CiliumLoadBalancerIPPool (v2, spec.blocks) ##########"
cat > /tmp/gwfix-bak/lbpool.yaml <<'YAML'
apiVersion: cilium.io/v2
kind: CiliumLoadBalancerIPPool
metadata:
  name: cilium-lb-pool
spec:
  blocks:
  - cidr: 10.100.10.251/32
YAML
kubectl apply -f /tmp/gwfix-bak/lbpool.yaml
sleep 5
kubectl get ciliumloadbalancerippool
echo "--- pool detail ---"
kubectl get ciliumloadbalancerippool cilium-lb-pool -o yaml | sed -n '/^spec:/,$p'
echo
echo "########## STEP 2: leftover kube-vip test IPs from deleted services ##########"
ip -o addr show | grep -E '10.100.10.(252|254)'
echo "--- kube-vip release log ---"
for p in $(kubectl -n kube-system get pod -o name | grep kube-vip); do kubectl -n kube-system logs $p --tail=40 2>&1 | grep -E 'Release|remove|252|254'; done
echo "--- removing stale .252/.254 (services deleted) ---"
ip addr del 10.100.10.252/32 dev ens3 2>&1 || echo "(252 already gone)"
ip addr del 10.100.10.254/32 dev ens3 2>&1 || echo "(254 already gone)"
sleep 3
ip -o addr show | grep 10.100.10.25 || echo "(only .250/.251 expected now)"
echo
echo "########## STEP 3: DURABILITY TEST - delete managed svc, let Cilium recreate ##########"
kubectl -n gateway delete svc cilium-gateway-monitoring-gateway
for i in 1 2 3 4 5 6 7 8; do
  sleep 10
  S=$(kubectl -n gateway get svc cilium-gateway-monitoring-gateway -o jsonpath='{.status.loadBalancer.ingress}' 2>/dev/null)
  A=$(kubectl get gateway -n gateway monitoring-gateway -o jsonpath='{.status.addresses[*].value}' 2>/dev/null)
  echo "t=$((i*10))s svc.ingress=$S gateway.address=$A"
  [ -n "$S" ] && break
done
echo "--- svc annotations after recreate ---"
kubectl -n gateway get svc cilium-gateway-monitoring-gateway -o jsonpath='{.metadata.annotations}'; echo
echo
echo "########## STEP 4: final state ##########"
kubectl get gateway -n gateway
kubectl get gateway -n gateway -o jsonpath='{range .status.conditions[*]}{.type}={.status}/{.reason} msg={.message}{"\n"}{end}'
echo
kubectl get httproute -A
kubectl get httproute -A -o jsonpath='{range .items[*]}{.metadata.name}{"  "}{range .status.parents[*].conditions[*]}{.type}={.status}/{.reason} {end}{"\n"}{end}'
echo
kubectl get ciliumloadbalancerippool
echo
echo "--- VIPs on control-01 ens3 ---"
ip -o addr show ens3 | grep 10.100.10.25
echo
echo "########## STEP 5: curl matrix through Gateway IP ##########"
IP=10.100.10.251
echo "grafana  /login : $(curl -s -o /dev/null -w '%{http_code}' --max-time 10 -H 'Host: grafana.wuxing.local' http://$IP/login)"
echo "grafana  /      : $(curl -s -o /dev/null -w '%{http_code}' --max-time 10 -H 'Host: grafana.wuxing.local' http://$IP/)"
echo "prometheus /graph: $(curl -s -o /dev/null -w '%{http_code}' --max-time 10 -H 'Host: prometheus.wuxing.local' http://$IP/graph)"
echo "prometheus /-/healthy: $(curl -s -o /dev/null -w '%{http_code}' --max-time 10 -H 'Host: prometheus.wuxing.local' http://$IP/-/healthy)"
echo "alertmanager /  : $(curl -s -o /dev/null -w '%{http_code}' --max-time 10 -H 'Host: alertmanager.wuxing.local' http://$IP/)"
echo "longhorn /      : $(curl -s -o /dev/null -w '%{http_code}' --max-time 10 -H 'Host: longhorn.wuxing.local' http://$IP/)"
echo "no host (catch-all grafana): $(curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://$IP/login)"
echo
echo "--- grafana /login full headers (proof) ---"
curl -s -D - -o /dev/null --max-time 10 -H 'Host: grafana.wuxing.local' http://$IP/login | head -14
echo
echo "--- grafana page title (proof it is really Grafana) ---"
curl -s --max-time 10 -H 'Host: grafana.wuxing.local' http://$IP/login | grep -oE '<title>[^<]*</title>|Grafana' | head -3
