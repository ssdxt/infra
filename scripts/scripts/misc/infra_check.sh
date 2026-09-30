#!/bin/bash
echo "=== docker-compose 版本 ==="
docker-compose --version 2>&1
echo "=== 各 yaml 目录 .env 是否存在 ==="
for d in /root/apps/docker/holarfileparse /root/sherpa/docker /root/embed /root/llm/docker_2/mineru_2509_1.2b /root/asr_work/holarasr_online /root/asr_work/docker /data/aippt /root/apps/docker/holarchat /opt/1panel/apps/local/holaros/holaros /root/work/holarvm /root/work /opt/1panel/apps/local/holarkanban/HolarKanban /opt/1panel/apps/local/holartts/holartts; do
  if [ -f "$d/.env" ]; then echo "ENV_OK    $d"; else echo "NO_ENV    $d"; fi
done
echo "=== aippt 全部容器状态(含停止的) ==="
docker ps -a --filter name=aippt --format "{{.Names}}\t{{.Status}}"
echo "=== aippt depends_on 依赖 ==="
grep -n -B1 -A8 "depends_on" /data/aippt/docker-compose.yml 2>/dev/null | head -80
echo "=== work 项目容器状态 ==="
docker ps -a --filter name=pg --filter name=mysql --filter name=minio --filter name=mongo --filter name=one-api --filter name=redis --filter name=deepdoc --format "{{.Names}}\t{{.Status}}"
echo "=== holarvm 全部容器 ==="
docker ps -a --filter name=meeting --format "{{.Names}}\t{{.Status}}"
