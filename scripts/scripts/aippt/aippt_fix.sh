#!/bin/bash
TS=$(date +%Y%m%d%H%M%S)
FILES="/data/aippt/api/api-config.yaml /data/aippt/agent/agent-config.yaml /data/aippt/fc/.env.prod /data/aippt/font/.env.prod /data/aippt/web/aippt.conf /data/aippt/docker-compose.yml"
for f in $FILES; do
  cp -a "$f" "$f.bak.$TS"
  sed -i 's/18\.18\.18\.60/192.168.21.105/g' "$f"
  echo "已处理 $f : 新IP $(grep -c '192.168.21.105' "$f") 处, 残留旧IP $(grep -c '18.18.18.60' "$f") 处"
done
echo
echo "=== 确认 api-config.yaml 关键行 ==="
grep -n -E '18\.18\.18\.60|192\.168\.21\.105' /data/aippt/api/api-config.yaml | head -20
echo
echo "=== 确认 agent-config.yaml 关键行 ==="
grep -n -E '18\.18\.18\.60|192\.168\.21\.105' /data/aippt/agent/agent-config.yaml | head -10
echo
echo "=== web 服务是否挂载 aippt.conf ==="
awk '/^  web:/,/^  fc:/' /data/aippt/docker-compose.yml | grep -E 'container_name|volumes|aippt.conf|ports' 
