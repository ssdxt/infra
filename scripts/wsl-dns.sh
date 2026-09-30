#!/bin/bash
echo "== 解析"
getent hosts harbor.wuxing.local || echo "DNS-FAIL"
grep -i harbor /etc/hosts 2>/dev/null || echo "no-hosts-entry"
echo "== 直连 IP 测"
curl -sk -o /dev/null -w 'ip29=%{http_code}\n' --max-time 8 https://10.100.10.29
echo "== 域名测（-k 忽略证书）"
curl -sk -o /dev/null -w 'domain=%{http_code}\n' --max-time 8 https://harbor.wuxing.local
echo "== 域名测（校验证书）"
curl -s -o /dev/null -w 'verify=%{http_code}\n' --max-time 8 https://harbor.wuxing.local 2>&1 | tail -2
echo "== docker daemon 配置"
cat /etc/docker/daemon.json 2>/dev/null || echo no-daemon-json