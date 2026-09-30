#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "########## FINAL STATE $(date -u +%Y-%m-%dT%H:%M:%SZ) ##########"
echo "--- apiserver ---"; kubectl get --raw='/readyz' 2>&1
echo
echo "--- CRITERION 1 ---"; kubectl get gateway -n gateway
echo
IP=$(kubectl get gateway -n gateway monitoring-gateway -o jsonpath='{.status.addresses[0].value}')
echo "--- CRITERION 2 (Gateway IP $IP) ---"
echo "curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: grafana.wuxing.local' http://$IP/login"
curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: grafana.wuxing.local' http://$IP/login
echo "--- all hosts ---"
for hp in "grafana.wuxing.local:/login" "prometheus.wuxing.local:/graph" "alertmanager.wuxing.local:/" "longhorn.wuxing.local:/"; do
  h=${hp%%:*}; p=${hp#*:}
  printf '  %-40s -> %s\n' "$h$p" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 -H "Host: $h" http://$IP$p)"
done
echo
echo "--- CRITERION 3 ---"; kubectl get httproute -A
echo
echo "--- VIPs on control-01 ---"; ip -o addr show ens3 | grep -oE '10\.100\.10\.[0-9]+/[0-9]+' | sort -u
echo "--- kube-vip restarts/leases ---"
kubectl -n kube-system get pod -o name | grep kube-vip | while read p; do echo "$p $(kubectl -n kube-system get $p -o jsonpath='{.status.containerStatuses[0].restartCount}')"; done
kubectl -n kube-system get lease plndr-cp-lock plndr-svcs-lock -o jsonpath='{range .items[*]}{.metadata.name}={.spec.holderIdentity}{"\n"}{end}'
echo
echo "--- pool ---"; kubectl get ciliumloadbalancerippool
echo "--- leftover test services ---"; kubectl get svc -A | grep -E 'test-lb|status-test' || echo "(clean)"
echo "--- backups ---"; ls /tmp/gwfix-bak/
