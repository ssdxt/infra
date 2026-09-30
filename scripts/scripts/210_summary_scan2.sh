#!/bin/bash
echo '===== docker-compose.yml: mysql 服务 ====='
grep -nA 28 '^  mysql:' /ManualAI/OmniKnow/docker-compose.yml | head -32
echo
echo '===== docker-compose.yml: redis 服务 ====='
grep -nA 22 '^  redis:' /ManualAI/OmniKnow/docker-compose.yml | head -26
echo
echo '===== 业务 .env 中的 DB/REDIS 键（密码打码） ====='
for f in /ManualAI/OmniKnow/omniknow2/envs/.env-assistant /ManualAI/OmniKnow/omniknow2/envs/.env-rag /ManualAI/OmniKnow/omniknow2/envs/.env-server /ManualAI/OmniKnow/omniknow2/assistant/.env /ManualAI/OmniKnow/omniknow2/server/.env /ManualAI/OmniKnow/omniknow2/parser/rag/.env; do
  echo "--- $f ---"
  grep -iE 'mysql|redis|db_|database|3306|6379|^DB|^REDIS|^MYSQL' "$f" 2>/dev/null | sed -E 's/(PASS[A-Z_]*=).*/\1***/I; s/(pass[a-z_]*=).*/\1***/I; s/(SECRET[A-Z_]*=).*/\1***/I' | head -25
done
echo
echo '===== 容器挂载（哪些配置宿主可改） ====='
for c in ai_server assistant parser cc-nginx; do
  echo "-- $c"
  docker inspect "$c" --format '{{json .Mounts}}' 2>/dev/null | tr '{' '\n' | grep -oE '"Source":"[^"]*"|"Destination":"[^"]*"' | paste - - 2>/dev/null | head -12
done
echo
echo '===== cc-mysql 环境 ====='
docker inspect cc-mysql --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | grep -iE 'MYSQL|PASS' | sed -E 's/(PASS[^=]*=).*/\1***/I'
echo '===== cc-redis 启动参数/env ====='
docker inspect cc-redis --format 'CMD: {{json .Config.Cmd}}' 2>/dev/null
docker inspect cc-redis --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | grep -iE 'redis|pass' | head -5
