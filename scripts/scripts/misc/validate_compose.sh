#!/bin/bash
echo "=== docker compose 插件 ==="
docker compose version 2>&1 | head -2
echo "=== 外部网络 ==="
docker network ls | grep -E 'gptnetwork|NAME'
echo "=== 逐个验证 compose 文件可解析 ==="
for pair in \
  "/root/work|docker-compose-database.yaml" \
  "/root/work|docker-compose-oneapi.yml" \
  "/root/work|docker-compose-deepdoc.yml" \
  "/root/embed|docker-compose-embed.yml" \
  "/root/sherpa/docker|docker-compose.yml" \
  "/root/llm/docker_2/mineru_2509_1.2b|docker-compose.yml" \
  "/root/asr_work/docker|docker-compose.yml" \
  "/root/asr_work/holarasr_online|docker-compose.yml" \
  "/root/apps/docker/holarfileparse|docker-compose.yml" \
  "/data/aippt|docker-compose.yml" \
  "/root/apps/docker/holarchat|docker-compose.yml" \
  "/root/work/holarvm|docker-compose.yml" \
  "/opt/1panel/apps/local/holaros/holaros|docker-compose.yml" \
  "/opt/1panel/apps/local/holarkanban/HolarKanban|docker-compose.yml" \
  "/opt/1panel/apps/local/holartts/holartts|docker-compose.yml" ; do
  dir="${pair%%|*}"; file="${pair##*|}"
  if (cd "$dir" && docker-compose -f "$file" config -q) 2>/tmp/cerr; then
    echo "OK    $dir/$file"
  else
    echo "FAIL  $dir/$file : $(head -3 /tmp/cerr)"
  fi
done
echo "=== aippt restart 策略 ==="
grep -n -B3 'restart:' /data/aippt/docker-compose.yml | head -50
