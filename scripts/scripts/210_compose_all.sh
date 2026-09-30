#!/bin/bash
echo '===== 1. 全盘 compose 文件清单 ====='
find / -maxdepth 6 \( -name 'docker-compose*.yml' -o -name 'docker-compose*.yaml' -o -name 'compose.yaml' -o -name 'compose.yml' \) 2>/dev/null | grep -vE '^/(proc|sys|dev)' | sort
echo
echo '===== 2. omniknow2 内部结构(2层) ====='
find /ManualAI/OmniKnow/omniknow2 -maxdepth 2 -type d 2>/dev/null | sort | head -30
echo
echo '===== 3. 各嵌套 compose 的 services + image 一览 ====='
for f in /ManualAI/OmniKnow/omniknow2/docker-compose.yaml /ManualAI/OmniKnow/omniknow2/server/docker-compose.yaml /ManualAI/OmniKnow/omniknow2/assistant/docker-compose.yml /ManualAI/OmniKnow/omniknow2/parser/docker-compose.yml /ManualAI/OmniKnow/data/mineru/docker-compose.yml; do
  echo "--- $f"
  grep -nE '^  [a-zA-Z0-9_-]+:|image:|container_name:|env_file:' "$f" 2>/dev/null | head -15
done
echo
echo '===== 4. 运行中容器 -> config_files 全集 ====='
for c in $(docker ps -a --format '{{.Names}}'); do
  f=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}' "$c" 2>/dev/null)
  [ -n "$f" ] && echo "$f"
done | sort -u
