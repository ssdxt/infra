#!/bin/bash
echo '== 完整 omniknow.conf =='
docker exec cc-nginx cat /etc/nginx/subconf/omniknow.conf 2>/dev/null
echo '== cc-nginx 网络 =='
docker inspect cc-nginx --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null
echo '== ai_server/assistant 网络 =='
docker inspect ai_server --format 'ai_server: {{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null
docker inspect assistant --format 'assistant: {{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null
echo '== cc-nginx 能否解析业务容器名 =='
docker exec cc-nginx sh -c 'getent hosts ai_server assistant 2>&1; which curl wget 2>/dev/null' 2>/dev/null
echo '== cc-nginx mounts（conf 是否挂载） =='
docker inspect cc-nginx --format '{{json .Mounts}}' 2>/dev/null | head -c 600
echo
echo '== 从 cc-nginx 直接测容器名可达性 =='
docker exec cc-nginx sh -c 'curl -s -o /dev/null -w "ai_server:8375 => %{http_code}\n" --max-time 5 http://ai_server:8375/ 2>&1 || wget -qO- --timeout=5 http://ai_server:8375/ 2>&1 | head -c 100' 2>/dev/null
docker exec cc-nginx sh -c 'curl -s -o /dev/null -w "assistant:8366 => %{http_code}\n" --max-time 5 http://assistant:8366/ 2>&1 || echo "no curl"' 2>/dev/null
