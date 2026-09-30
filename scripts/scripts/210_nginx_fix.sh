#!/bin/bash
CONF=/ManualAI/OmniKnow/data/nginx/subconf/omniknow.conf
echo '== backup =='
cp "$CONF" "$CONF.bak.$(date +%H%M%S)" && echo 'backed up'
echo '== fix proxy targets =='
sed -i 's|proxy_pass http://192.168.0.23:8366/;|proxy_pass http://assistant:8366/;|' "$CONF"
sed -i 's|proxy_pass http://192.168.0.23:8375/;|proxy_pass http://ai_server:8375/;|' "$CONF"
sed -i 's|server_name  115.120.240.126;|server_name  _;|' "$CONF"
echo '== after =='
grep -nE 'server_name|proxy_pass' "$CONF"
echo '== reload nginx =='
docker exec cc-nginx nginx -t 2>&1 | head -3
docker exec cc-nginx nginx -s reload 2>&1 && echo 'nginx reloaded'
sleep 2
echo '== 从 210 本机经 nginx 测后端 =='
curl -s -o /dev/null -w '/backend/ => %{http_code}\n' --max-time 8 http://localhost:8378/backend/
curl -s -o /dev/null -w '/knowledge_api/ => %{http_code}\n' --max-time 8 http://localhost:8378/knowledge_api/
echo '== nginx 最近错误日志 =='
docker exec cc-nginx sh -c 'tail -3 /var/log/nginx/error.log 2>/dev/null' 2>/dev/null
