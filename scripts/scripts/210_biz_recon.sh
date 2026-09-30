#!/bin/bash
echo '== ngrok 隧道 URL =='
curl -s --max-time 8 http://127.0.0.1:4040/api/tunnels 2>/dev/null | grep -oE '"public_url":"[^"]*"' | head -5
echo
echo '== zellij 会话 =='
zellij list-sessions 2>&1 | head -5
echo
echo '== cc-nginx 8378 相关配置 =='
docker exec cc-nginx sh -c 'grep -rn "8378\|listen\|server_name\|proxy_pass" /etc/nginx/conf.d/ /etc/nginx/nginx.conf 2>/dev/null' 2>/dev/null | head -25
echo
echo '== nginx 配置文件清单 =='
docker exec cc-nginx sh -c 'ls /etc/nginx/conf.d/ 2>/dev/null; echo ---; ls /etc/nginx/ 2>/dev/null | head' 2>/dev/null
