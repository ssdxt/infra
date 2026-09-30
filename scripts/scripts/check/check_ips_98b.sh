#!/bin/bash
echo "=== .98 本机网卡 IP ==="
ip -4 addr show | grep -E '^[0-9]+:|inet '
echo "=== 路由/网关 ==="
ip route | head -5
echo "=== netplan 配置 ==="
ls /etc/netplan/ 2>/dev/null && cat /etc/netplan/*.yaml 2>/dev/null
echo "=== /etc/hosts ==="
cat /etc/hosts 2>/dev/null
