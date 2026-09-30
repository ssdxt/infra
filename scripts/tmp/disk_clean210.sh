#!/bin/bash
echo "== big container logs =="
find /data/docker/containers -name '*-json.log' -size +100M -exec ls -lh {} \; 2>/dev/null | head -8
echo "== truncate big container logs =="
find /data/docker/containers -name '*-json.log' -size +100M -exec truncate -s 0 {} \; 2>/dev/null && echo truncated
echo "== nginx proxy_temp/cache clean =="
docker exec cc-nginx sh -c 'rm -rf /var/cache/nginx/proxy_temp/* /var/cache/nginx/client_temp/* 2>/dev/null; du -sh /var/cache/nginx 2>/dev/null' 
echo "== /var/log old clean =="
find /var/log -name '*.log.*' -o -name '*.gz' 2>/dev/null | head -5
echo "== df after =="
df -h / | tail -1
