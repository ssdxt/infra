#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
set -u
echo "########## ISOLATION TEST: drop Gateway spec.addresses, keep only the IP pool ##########"
kubectl -n gateway patch gateway monitoring-gateway --type json -p '[{"op":"remove","path":"/spec/addresses"}]'
sleep 3
kubectl -n gateway get gateway monitoring-gateway -o jsonpath='spec.addresses={.spec.addresses}'; echo
kubectl -n gateway delete svc cilium-gateway-monitoring-gateway
for i in 1 2 3 4 5 6; do
  sleep 10
  S=$(kubectl -n gateway get svc cilium-gateway-monitoring-gateway -o jsonpath='{.status.loadBalancer.ingress}' 2>/dev/null)
  A=$(kubectl get gateway -n gateway monitoring-gateway -o jsonpath='{.status.addresses[*].value}' 2>/dev/null)
  P=$(kubectl get gateway -n gateway monitoring-gateway -o jsonpath='{.status.conditions[?(@.type=="Programmed")].status}' 2>/dev/null)
  echo "t=$((i*10))s svc.ingress=$S gateway.address=$A programmed=$P"
  [ -n "$S" ] && break
done
echo "--- svc annotations (pool-driven allocation?) ---"
kubectl -n gateway get svc cilium-gateway-monitoring-gateway -o jsonpath='{.metadata.annotations}'; echo
echo
echo "########## WAIT 90s for stability ##########"
sleep 90
kubectl get gateway -n gateway
kubectl get ciliumloadbalancerippool
echo "--- VIPs on ens3 ---"
ip -o addr show ens3 | grep 10.100.10.25
echo
echo "########## FINAL VERIFICATION ##########"
echo "### C1: gateway"
kubectl get gateway -n gateway
kubectl get gateway -n gateway -o jsonpath='{range .status.conditions[*]}  {.type}={.status} reason={.reason} msg={.message}{"\n"}{end}'
echo "### C2: curl grafana via gateway IP"
IP=$(kubectl get gateway -n gateway monitoring-gateway -o jsonpath='{.status.addresses[0].value}')
echo "GATEWAY_IP=$IP"
echo -n "  /login -> "; curl -s -o /dev/null -w '%{http_code}\n' --max-time 10 -H 'Host: grafana.wuxing.local' http://$IP/login
echo -n "  / -> "; curl -s -o /dev/null -w '%{http_code}\n' --max-time 10 -H 'Host: grafana.wuxing.local' http://$IP/
echo "### C3: httproutes"
kubectl get httproute -A
kubectl get httproute -A -o jsonpath='{range .items[*]}{.metadata.name}{"  "}{range .status.parents[*].conditions[*]}{.type}={.status}/{.reason} {end}{"\n"}{end}'
echo
echo "### extra hosts"
for pair in "prometheus.wuxing.local:/graph" "alertmanager.wuxing.local:/" "longhorn.wuxing.local:/"; do
  h=${pair%%:*}; p=${pair#*:}
  echo -n "  $h$p -> "; curl -s -o /dev/null -w '%{http_code}\n' --max-time 10 -H "Host: $h" http://$IP$p
done
echo
echo "### no unrelated changes: cilium/monitoring pod health"
kubectl -n kube-system get pods | grep -E 'cilium-operator|cilium-88lxj|cilium-envoy-c4vmr'
kubectl -n monitoring get pods | grep -vE 'Running|Completed' | head
echo "(any line above = not Running)"
echo
echo "### files changed (backups kept)"
ls -l /tmp/gwfix-bak/
echo
echo "### gateway ns services (ExternalName ones now unused, left in place)"
kubectl -n gateway get svc
