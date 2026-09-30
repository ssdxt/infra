#!/bin/bash
echo "=== 本机网卡 IP ==="
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
echo "=== 部署配置中的硬编码 IP (yaml/env/conf) ==="
grep -rn -E '(192\.168|10\.|172\.(1[6-9]|2[0-9]|3[01]))\.[0-9]+\.[0-9]+' \
  /root/apps /data/aippt /root/work /opt/1panel/apps /root/embed /root/sherpa /root/llm /root/asr_work \
  --include='*.yml' --include='*.yaml' --include='*.env' --include='*.conf' --include='*.json' --include='*.sh' 2>/dev/null | head -50
echo "=== nginx 反代配置中的 IP ==="
grep -rn -E 'proxy_pass|server [0-9]|192\.168|10\.' /etc/nginx/conf.d/ 2>/dev/null | head -30
echo "=== box_manager 中的 IP ==="
grep -rn -E '192\.168|10\.' /root/box_manager 2>/dev/null --include='*.yaml' --include='*.yml' --include='*.json' --include='*.env' | head -20
