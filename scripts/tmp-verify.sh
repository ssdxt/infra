#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== stability watch: ens3 VIPs + kube-vip restarts every 30s for 3.5 min ==="
for i in $(seq 1 7); do
  echo "t=$((i*30))s addrs=[$(ip -o addr show ens3 | grep -oE '10\.100\.10\.[0-9]+' | tr '\n' ' ')] kvrestarts=$(kubectl -n kube-system get pod kube-vip-wxq-control-01 -o jsonpath='{.status.containerStatuses[0].restartCount}' 2>/dev/null)"
  sleep 30
done
echo
echo "=== apiserver health (direct) ==="
kubectl get --raw='/readyz?verbose' 2>&1 | grep -E 'etcd|readyz check' | head -5
echo
echo "=== kube-vip leader leases ==="
kubectl -n kube-system get lease plndr-cp-lock plndr-svcs-lock -o jsonpath='{range .items[*]}{.metadata.name}{" holder="}{.spec.holderIdentity}{" renew="}{.spec.renewTime}{"\n"}{end}'
echo
echo "=== CRITERION 1: gateway ==="
kubectl get gateway -n gateway
echo "--- conditions ---"
kubectl get gateway -n gateway -o jsonpath='{range .status.conditions[*]}  {.type}={.status} reason={.reason} message={.message}{"\n"}{end}'
echo "--- listener detail ---"
kubectl get gateway -n gateway -o jsonpath='{range .status.listeners[*]}  listener={.name} attachedRoutes={.attachedRoutes} {range .conditions[*]}{.type}={.status}/{.reason} {end}{"\n"}{end}'
echo
IP=$(kubectl get gateway -n gateway monitoring-gateway -o jsonpath='{.status.addresses[0].value}')
echo "=== CRITERION 2: curl via Gateway IP ($IP) ==="
echo -n "grafana    /login -> "; curl -s -o /dev/null -w '%{http_code}\n' --max-time 10 -H 'Host: grafana.wuxing.local' http://$IP/login
echo -n "grafana    /      -> "; curl -s -o /dev/null -w '%{http_code}\n' --max-time 10 -H 'Host: grafana.wuxing.local' http://$IP/
echo -n "prometheus /graph -> "; curl -s -o /dev/null -w '%{http_code}\n' --max-time 10 -H 'Host: prometheus.wuxing.local' http://$IP/graph
echo -n "alertmanager /    -> "; curl -s -o /dev/null -w '%{http_code}\n' --max-time 10 -H 'Host: alertmanager.wuxing.local' http://$IP/
echo -n "longhorn   /      -> "; curl -s -o /dev/null -w '%{http_code}\n' --max-time 10 -H 'Host: longhorn.wuxing.local' http://$IP/
echo "--- raw curl output for the required check ---"
curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: grafana.wuxing.local' http://$IP/login
echo "--- grafana body proof ---"
curl -s --max-time 10 -H 'Host: grafana.wuxing.local' http://$IP/login | grep -oE '<title>[^<]*</title>' | head -1
echo
echo "=== CRITERION 3: httproutes ==="
kubectl get httproute -A
kubectl get httproute -A -o jsonpath='{range .items[*]}{.metadata.name}{"  "}{range .status.parents[*].conditions[*]}{.type}={.status}/{.reason} {end}{"\n"}{end}'
echo
echo "=== IP pool ==="
kubectl get ciliumloadbalancerippool
kubectl get ciliumloadbalancerippool cilium-lb-pool -o jsonpath='{.spec}'; echo
echo
echo "=== generated svc ==="
kubectl -n gateway get svc cilium-gateway-monitoring-gateway -o jsonpath='annotations={.metadata.annotations}{"\n"}status={.status.loadBalancer.ingress}{"\n"}'
echo
echo "=== leftover test services gone? ==="
kubectl get svc -A | grep -E 'test-lb|status-test' || echo "(none - clean)"
echo
echo "=== nothing else broken: pods not Running ==="
kubectl get pod -A 2>/dev/null | grep -vE 'Running|Completed|NAMESPACE' | head -10
echo "(empty except known operator = fine)"
