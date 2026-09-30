#!/bin/bash
echo "=== 105 全部容器(含停止) ==="
docker ps -a --format "{{.Names}} | {{.Status}} | {{.Image}}" | sort
echo
echo "=== 容器 -> compose 映射 ==="
for c in $(docker ps -a --format '{{.Names}}'); do
  proj=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$c" 2>/dev/null)
  files=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project.config_files"}}' "$c" 2>/dev/null)
  if [ -n "$proj" ]; then
    echo "$c | PROJ=$proj | $files"
  else
    echo "$c | (无compose标签)"
  fi
done
echo
echo "=== /ManualAI 是否存在(98风格的部署) ==="
ls /ManualAI 2>/dev/null || echo "无 /ManualAI"
echo
echo "=== 退出状态的容器日志 ==="
for c in $(docker ps -a --format '{{.Names}}' | while read n; do s=$(docker inspect -f '{{.State.Status}}' "$n"); [ "$s" = "exited" ] && echo "$n"; done); do
  echo "--- $c (退出码 $(docker inspect -f '{{.State.ExitCode}}' "$c")) ---"
  docker logs "$c" --tail 8 2>&1 | tail -8
  echo
done
