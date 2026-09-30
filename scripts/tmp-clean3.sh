#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== step 1: recreate the 4 test services kube-vip still has cached ==="
for n in test-lb test-lb-ann; do
  kubectl create svc loadbalancer $n --tcp=80:80 --dry-run=client -o yaml | kubectl apply -f - >/dev/null 2>&1
done
kubectl create svc loadbalancer test-lb-static --tcp=80:80 --dry-run=client -o yaml > /tmp/a.yaml
python3 - <<'PY'
p='/tmp/a.yaml'; s=open(p).read()
s=s.replace('  type: LoadBalancer','  loadBalancerIP: 10.100.10.252\n  type: LoadBalancer')
open(p,'w').write(s)
PY
kubectl apply -f /tmp/a.yaml >/dev/null
kubectl create svc loadbalancer status-test --tcp=80:80 --dry-run=client -o yaml > /tmp/b.yaml
python3 - <<'PY'
p='/tmp/b.yaml'; s=open(p).read()
s=s.replace('  type: LoadBalancer','  loadBalancerIP: 10.100.10.254\n  type: LoadBalancer')
open(p,'w').write(s)
PY
kubectl apply -f /tmp/b.yaml >/dev/null
kubectl -n default get svc
echo
echo "=== step 2: wait 40s for kube-vip to register them ==="
sleep 40
kubectl -n kube-system logs kube-vip-wxq-control-01 --tail=25 2>&1 | grep -E 'adding VIP|Removed|advertised' | tail -10
echo
echo "=== step 3: delete them (clean lifecycle so kube-vip drops cache) ==="
kubectl delete svc test-lb test-lb-ann test-lb-static status-test -n default
sleep 45
echo "--- kube-vip log after delete ---"
kubectl -n kube-system logs kube-vip-wxq-control-01 --tail=40 2>&1 | grep -E 'Removed|advertised|deleted|Re-applying' | tail -12
echo
echo "=== step 4: remove orphan addresses, observe 120s ==="
ip addr del 10.100.10.252/32 dev ens3 2>&1
ip addr del 10.100.10.254/32 dev ens3 2>&1
for i in $(seq 1 8); do
  sleep 15
  echo "t=$((i*15))s: [$(ip -o addr show ens3 | grep -oE '10\.100\.10\.25[0-9]' | tr '\n' ' ')]"
done
echo
echo "=== step 5: gateway still healthy? ==="
kubectl get gateway -n gateway
IP=$(kubectl get gateway -n gateway monitoring-gateway -o jsonpath='{.status.addresses[0].value}')
echo -n "grafana /login -> "; curl -s -o /dev/null -w '%{http_code}\n' --max-time 10 -H 'Host: grafana.wuxing.local' http://$IP/login
