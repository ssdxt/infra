#!/bin/bash
echo "== HOST =="
hostname; hostnamectl 2>/dev/null | grep -iE 'Static hostname|Operating System|Kernel'
echo "== ACTIVE NM CONNS =="
nmcli -t -f NAME,TYPE,DEVICE,STATE con show --active 2>/dev/null
echo "== NM ipv4.method (all conns) =="
nmcli -t -f NAME,DEVICE,ipv4.method,IP4.ADDRESS,IP4.GATEWAY con show 2>/dev/null
echo "== NM DEVICE STATUS =="
nmcli -t device status 2>/dev/null
echo "== NETPLAN FILES =="
ls -1 /etc/netplan 2>/dev/null
for f in /etc/netplan/*; do
  echo "-- $f"
  grep -vE '^\s*(#|$)' "$f" 2>/dev/null
done
echo "== /etc/network/interfaces =="
grep -vE '^\s*(#|$)' /etc/network/interfaces 2>/dev/null
echo "== systemd-networkd config =="
ls -1 /etc/systemd/network 2>/dev/null
echo "== IP ADDR =="
ip -4 addr show | grep -E '^[0-9]+:|inet '
echo "== ROUTE =="
ip route
echo "== DHCP LEASES =="
ls -la /var/lib/dhcp /run/systemd/netif/leases 2>/dev/null
cat /run/systemd/netif/leases/* 2>/dev/null | head -40
echo "== RESOLV.CONF =="
cat /etc/resolv.conf 2>/dev/null
echo "== DHCP CLIENT PIDS =="
ps -ef | grep -iE 'dhclient|dhcpcd|networkd' | grep -v grep
