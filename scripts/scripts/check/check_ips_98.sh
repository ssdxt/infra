#!/bin/bash
echo "=== .98 本机网卡 IP ==="
ip -4 addr show | grep -E '^[0-9]+:|inet '
echo "=== 路由/网关 ==="
ip route | head -5
echo "=== netplan 配置 ==="
ls /etc/netplan/ 2>/dev/null && cat /etc/netplan/*.yaml 2>/dev/null
echo "=== NetworkManager 连接 ==="
nmcli -t -f NAME,TYPE con show 2>/dev/null | head -5
nmcli -t -f IP4.ADDRESS,IP4.GATEWAY con show 2>/dev/null | head -5
echo "=== /etc/hosts ==="
cat /etc/hosts 2>/dev/null
