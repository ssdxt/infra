#!/bin/bash
echo "===== 容器 -> compose 项目/yaml 映射 ====="
for c in $(docker ps --format '{{.Names}}'); do
  proj=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$c" 2>/dev/null)
  files=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project.config_files"}}' "$c" 2>/dev/null)
  wdir=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' "$c" 2>/dev/null)
  service=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.service"}}' "$c" 2>/dev/null)
  if [ -n "$proj" ]; then
    echo "CONTAINER=$c | SERVICE=$service | PROJECT=$proj | WORKDIR=$wdir | YAML=$files"
  else
    echo "CONTAINER=$c | (no compose labels - started via docker run or other)"
  fi
done
