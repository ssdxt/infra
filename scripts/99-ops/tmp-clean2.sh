#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== before ==="
ip -o addr show ens3 | grep 10.100.10.25
echo "=== del orphan test IPs .252/.254 (their Services no longer exist) ==="
ip addr del 10.100.10.252/32 dev ens3 2>&1; echo "rc252=$?"
ip addr del 10.100.10.254/32 dev ens3 2>&1; echo "rc254=$?"
echo "=== observe every 15s for 180s ==="
for i in $(seq 1 12); do
  sleep 15
  echo "t=$((i*15))s: [$(ip -o addr show ens3 | grep -oE '10\.100\.10\.25[0-9]' | tr '\n' ' ')]"
done
echo "=== kube-vip recent log ==="
kubectl -n kube-system logs kube-vip-wxq-control-01 --tail=15 2>&1 | tail -8
