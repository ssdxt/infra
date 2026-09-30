#!/bin/bash
echo '== nginx.conf head =='
docker exec cc-nginx sh -c 'head -50 /etc/nginx/nginx.conf' 2>/dev/null
echo '== subconf 内容 =='
docker exec cc-nginx sh -c 'ls /etc/nginx/subconf/ 2>/dev/null' 2>/dev/null
echo '== 全配置 grep listen/server_name/proxy_pass =='
docker exec cc-nginx sh -c 'grep -rnE "listen|server_name|proxy_pass|location" /etc/nginx/ --include="*.conf" 2>/dev/null' 2>/dev/null | head -40
