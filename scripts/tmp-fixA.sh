#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== backup gateway svc ====="
kubectl get svc -n gateway cilium-gateway-monitoring-gateway -o yaml > /tmp/gwsvc.bak.yaml
wc -l /tmp/gwsvc.bak.yaml
echo
echo "===== STEP A: patch generated svc with spec.loadBalancerIP=10.100.10.251 ====="
kubectl -n gateway patch svc cilium-gateway-monitoring-gateway --type merge -p '{"spec":{"loadBalancerIP":"10.100.10.251"}}'
for i in 1 2 3 4 5 6; do
  sleep 10
  echo "--- t=$((i*10))s svc.ingress: $(kubectl get svc -n gateway cilium-gateway-monitoring-gateway -o jsonpath='{.status.loadBalancer.ingress}') | spec.loadBalancerIP=$(kubectl get svc -n gateway cilium-gateway-monitoring-gateway -o jsonpath='{.spec.loadBalancerIP}')"
done
echo
echo "===== gateway status ====="
kubectl get gateway -n gateway
kubectl get gateway -n gateway -o jsonpath='{range .items[*].status.addresses[*]}{.type}={.value}{"\n"}{end}'
echo
echo "===== kube-vip log for 251 ====="
for p in $(kubectl -n kube-system get pod -o name | grep kube-vip); do kubectl -n kube-system logs $p --tail=60 2>&1 | grep -E '251|gateway|VIP' | tail -10; done
echo
echo "===== ip addr 251 ====="
ip -o addr show | grep -E '10.100.10.251' || echo "(251 not on any interface)"
echo
echo "===== curl test ====="
for h in grafana prometheus alertmanager longhorn; do
  echo -n "$h -> "; curl -s -o /dev/null -w '%{http_code}\n' --max-time 8 -H "Host: $h.wuxing.local" http://10.100.10.251/login 2>&1 || echo "curl rc=$?"
done
