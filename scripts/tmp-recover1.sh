#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
K="kubectl --server=https://10.100.10.10:6443 --request-timeout=15s"
echo "=== A. apiserver directly (bypass VIP) ==="
$K get --raw='/readyz?verbose' 2>&1 | tail -6
echo
echo "=== B. leases ==="
$K -n kube-system get lease plndr-cp-lock plndr-svcs-lock -o jsonpath='{range .items[*]}{.metadata.name}{" holder="}{.spec.holderIdentity}{" renew="}{.spec.renewTime}{"\n"}{end}' 2>&1
echo
echo "=== C. control-01 ens3 addresses ==="
ip -o addr show ens3
echo
echo "=== D. who answers ARP for .250 / .251 ==="
for ip in 10.100.10.250 10.100.10.251; do
  ip neigh flush $ip 2>/dev/null
  ping -c 1 -W 2 $ip >/dev/null 2>&1
  echo "$ip -> neigh: $(ip neigh show $ip)"
done
echo
echo "=== E. kube-vip pods ==="
$K -n kube-system get pod -o wide 2>&1 | grep kube-vip
echo
echo "=== F. control-01 kube-vip log tail ==="
$K -n kube-system logs kube-vip-wxq-control-01 --tail=30 2>&1 | tail -20
echo
echo "=== G. control-02 kube-vip log tail ==="
$K -n kube-system logs kube-vip-wxq-control-02 --tail=20 2>&1 | tail -12
echo
echo "=== H. control-03 kube-vip log tail ==="
$K -n kube-system logs kube-vip-wxq-control-03 --tail=20 2>&1 | tail -12
