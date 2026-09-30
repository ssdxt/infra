#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== restart count before ==="
kubectl -n kube-system get pod kube-vip-wxq-control-01 -o jsonpath='restarts={.status.containerStatuses[0].restartCount} started={.status.containerStatuses[0].state.running.startedAt}'; echo
echo
echo "=== find kube-vip container on this node ==="
which crictl || ls -l /usr/local/bin/crictl /usr/bin/crictl 2>/dev/null
CR=$(crictl ps --name kube-vip -q 2>&1 | head -1)
echo "container=$CR"
crictl ps --name kube-vip 2>&1 | head -3
echo
echo "=== stop container (kubelet restarts it from the static manifest) ==="
crictl stop "$CR" 2>&1
for i in $(seq 1 20); do
  sleep 5
  R=$(kubectl -n kube-system get pod kube-vip-wxq-control-01 -o jsonpath='{.status.containerStatuses[0].restartCount}/{.status.containerStatuses[0].ready}' 2>/dev/null)
  echo "t=$((i*5))s restarts/ready=$R addrs=[$(ip -o addr show ens3 | grep -oE '10\.100\.10\.25[0-9]' | tr '\n' ' ')]"
  case "$R" in 71/true|7*/true|8*/true|9*/true) ;; esac
  [ "${R#*/}" = "true" ] && [ "${R%%/*}" -gt 70 ] && break
done
echo
echo "=== fresh kube-vip log (should start clean) ==="
kubectl -n kube-system logs kube-vip-wxq-control-01 --tail=25 2>&1 | tail -15
echo
echo "=== now remove orphan .252/.254 and observe 150s ==="
echo "before: [$(ip -o addr show ens3 | grep -oE '10\.100\.10\.25[0-9]' | tr '\n' ' ')]"
ip addr del 10.100.10.252/32 dev ens3 2>&1; echo "rc252=$?"
ip addr del 10.100.10.254/32 dev ens3 2>&1; echo "rc254=$?"
for i in $(seq 1 10); do
  sleep 15
  echo "t=$((i*15))s: [$(ip -o addr show ens3 | grep -oE '10\.100\.10\.25[0-9]' | tr '\n' ' ')]"
done
echo
echo "=== verify .250 apiserver VIP + gateway ==="
ping -c 2 -W 2 10.100.10.250 2>&1 | tail -3
kubectl -n kube-system get lease plndr-cp-lock plndr-svcs-lock -o jsonpath='{range .items[*]}{.metadata.name}{" holder="}{.spec.holderIdentity}{"\n"}{end}'
kubectl get gateway -n gateway
IP=$(kubectl get gateway -n gateway monitoring-gateway -o jsonpath='{.status.addresses[0].value}')
echo -n "grafana /login -> "; curl -s -o /dev/null -w '%{http_code}\n' --max-time 10 -H 'Host: grafana.wuxing.local' http://$IP/login
