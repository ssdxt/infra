#!/bin/bash
echo "=== /etc/network/interfaces ==="
cat /etc/network/interfaces 2>/dev/null
ls /etc/network/interfaces.d/ 2>/dev/null && cat /etc/network/interfaces.d/* 2>/dev/null
echo "=== NetworkManager 连接 ==="
nmcli -t -f NAME,TYPE,DEVICE con show 2>/dev/null | head -10
echo "=== enP7p1s0 连接的 IP 配置 ==="
for c in $(nmcli -t -f NAME,DEVICE con show 2>/dev/null | grep enP7p1s0 | cut -d: -f1); do
  echo "--- 连接: $c ---"
  nmcli -t -f ipv4.method,ipv4.addresses,ipv4.gateway,ipv4.dns con show "$c" 2>/dev/null
done
echo "=== 是否有 systemd-networkd ==="
ls /etc/systemd/network/ 2>/dev/null
echo "=== 历史命令里的静态IP配置痕迹 ==="
grep -rh -E 'ip addr add|ifconfig|192.168.21.98' /root/.bash_history /home/*/.bash_history 2>/dev/null | tail -10
