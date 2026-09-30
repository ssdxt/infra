#!/bin/bash
echo "=== .98 全部容器 ==="
docker ps -a --format "{{.Names}} | {{.Status}} | {{.Image}}"
echo
echo "=== 容器 -> compose 映射 ==="
for c in $(docker ps -a --format '{{.Names}}'); do
  proj=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$c" 2>/dev/null)
  files=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project.config_files"}}' "$c" 2>/dev/null)
  wdir=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' "$c" 2>/dev/null)
  if [ -n "$proj" ]; then
    echo "CONTAINER=$c | PROJECT=$proj | YAML=$files | WORKDIR=$wdir"
  else
    echo "CONTAINER=$c | (无compose标签 - docker run 启动)"
  fi
done
echo
echo "=== compose 版本 ==="
docker-compose --version 2>&1
docker compose version 2>&1
