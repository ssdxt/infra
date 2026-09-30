#!/bin/bash
echo '== omniknow-fixed.yml 定义的服务 =='
grep -nE '^  [a-zA-Z0-9_-]+:' /ManualAI/OmniKnow/docker-omniknow-fixed.yml
echo
echo '== docker-compose ps (omniknow 项目视角) =='
cd /ManualAI/OmniKnow && docker-compose -f docker-omniknow-fixed.yml ps 2>&1 | head -25
echo
echo '== 所有运行中的容器及 compose 归属 =='
for c in $(docker ps --format '{{.Names}}'); do
  proj=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$c" 2>/dev/null)
  svc=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.service"}}' "$c" 2>/dev/null)
  echo "$c | project=${proj:-无标签} | service=${svc:-无}"
done
