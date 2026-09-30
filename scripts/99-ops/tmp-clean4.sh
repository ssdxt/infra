#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== pre-check: leases ==="
kubectl -n kube-system get lease plndr-cp-lock plndr-svcs-lock -o jsonpath='{range .items[*]}{.metadata.name}{" holder="}{.spec.holderIdentity}{"\n"}{end}'
echo "=== pre-check: kube-vip pods ==="
kubectl -n kube-system get pod -o wide | grep kube-vip
echo
echo "=== restart kube-vip static pod on control-01 (kubelet recreates it) ==="
kubectl -n kube-system delete pod kube-vip-wxq-control-01
for i in $(seq 1 18); do
  sleep 5
  P=$(kubectl -n kube-system get pod kube-vip-wxq-control-01 -o jsonpath='{.status.phase}/{.status.containerStatuses[0].ready}' 2>/dev/null)
  echo "t=$((i*5))s pod=$P addrs=[$(ip -o addr show ens3 | grep -oE '10\.100\.10\.25[0-9]' | tr '\n' ' ')]"
  [ "$P" = "Running/true" ] && break
done
echo
echo "=== kube-vip fresh logs (manager rebuild) ==="
sleep 10
kubectl -n kube-system logs kube-vip-wxq-control-01 --tail=40 2>&1 | grep -E 'Starting|advertised|adding VIP|Re-applying|leadership|acquired|Releasing' | tail -20
echo
echo "=== remove orphan .252/.254 now that state is rebuilt ==="
echo "before: [$(ip -o addr show ens3 | grep -oE '10\.100\.10\.25[0-9]' | tr '\n' ' ')]"
ip addr del 10.100.10.252/32 dev ens3 2>&1; echo "rc252=$?"
ip addr del 10.100.10.254/32 dev ens3 2>&1; echo "rc254=$?"
echo "=== observe 150s ==="
for i in $(seq 1 10); do
  sleep 15
  echo "t=$((i*15))s: [$(ip -o addr show ens3 | grep -oE '10\.100\.10\.25[0-9]' | tr '\n' ' ')]"
done
echo
echo "=== check other control nodes for orphans ==="
echo "(local only - control-01)"
echo
echo "=== leases after ==="
kubectl -n kube-system get lease plndr-cp-lock plndr-svcs-lock -o jsonpath='{range .items[*]}{.metadata.name}{" holder="}{.spec.holderIdentity}{"\n"}{end}'
echo
echo "=== FINAL: gateway + curl ==="
kubectl get gateway -n gateway
IP=$(kubectl get gateway -n gateway monitoring-gateway -o jsonpath='{.status.addresses[0].value}')
echo "GATEWAY_IP=$IP"
echo -n "grafana /login -> "; curl -s -o /dev/null -w '%{http_code}\n' --max-time 10 -H 'Host: grafana.wuxing.local' http://$IP/login
echo -n "prometheus /graph -> "; curl -s -o /dev/null -w '%{http_code}\n' --max-time 10 -H 'Host: prometheus.wuxing.local' http://$IP/graph
echo -n "alertmanager / -> "; curl -s -o /dev/null -w '%{http_code}\n' --max-time 10 -H 'Host: alertmanager.wuxing.local' http://$IP/
kubectl get httproute -A -o jsonpath='{range .items[*]}{.metadata.name}{"  "}{range .status.parents[*].conditions[*]}{.type}={.status}/{.reason} {end}{"\n"}{end}'
echo
echo "=== apiserver VIP sanity (did .250 survive?) ==="
ping -c 2 -W 2 10.100.10.250 2>&1 | tail -3
