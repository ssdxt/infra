#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== 1. current svc + gateway state (persistence check) ====="
kubectl get svc -n gateway cilium-gateway-monitoring-gateway -o jsonpath='{.spec.loadBalancerIP}|{.spec.loadBalancerClass}|{.status.loadBalancer.ingress}'; echo
kubectl get gateway -n gateway
echo
echo "===== 2. HTTPROUTES full ====="
kubectl get httproute -A -o yaml
echo
echo "===== 3. ReferenceGrants (all ns) ====="
kubectl get referencegrant -A 2>&1 || true
echo
echo "===== 4. monitoring services (real backends) ====="
kubectl -n monitoring get svc -o wide
echo
echo "===== 5. longhorn svc ====="
kubectl -n longhorn-system get svc longhorn-frontend -o wide
echo
echo "===== 6. envoy admin / cilium-envoy logs 503 ====="
for p in $(kubectl -n kube-system get pod -o name | grep 'cilium-envoy' | head -2); do echo "--- $p ---"; kubectl -n kube-system logs $p --tail=40 2>&1 | tail -20; done
echo
echo "===== 7. cilium agent (control-01) gateway/envoy config errors ====="
kubectl -n kube-system logs cilium-88lxj --tail=200 2>&1 | grep -iE 'gateway|envoy|backend|error' | tail -30
echo
echo "===== 8. Gateway spec.addresses support test: patch Gateway ====="
kubectl get gateway -n gateway monitoring-gateway -o yaml > /tmp/gw.bak.yaml
kubectl -n gateway patch gateway monitoring-gateway --type merge -p '{"spec":{"addresses":[{"type":"IPAddress","value":"10.100.10.251"}]}}' 2>&1
sleep 15
echo "--- gateway after spec.addresses patch ---"
kubectl get gateway -n gateway
kubectl get gateway -n gateway -o jsonpath='{.items[0].spec.addresses}'; echo
echo "--- svc after ---"
kubectl get svc -n gateway cilium-gateway-monitoring-gateway -o jsonpath='{.spec.loadBalancerIP}|{.spec.loadBalancerClass}|{.status.loadBalancer.ingress}'; echo
