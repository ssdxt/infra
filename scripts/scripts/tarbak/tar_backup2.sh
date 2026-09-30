#!/bin/bash
cd /
FILES=""
for f in \
  root/work/docker-compose-database.yaml \
  root/work/docker-compose-oneapi.yml \
  root/work/docker-compose-deepdoc.yml \
  root/embed/docker-compose-embed.yml \
  root/sherpa/docker/docker-compose.yml \
  root/llm/docker_2/mineru_2509_1.2b/docker-compose.yml \
  root/llm/docker_2/qwen3_30b_a3b_instruct_nvfp4/docker-compose.yml \
  root/llm/docker_2/qwen3_next_80b_a3b_instruct_nvfp4/docker-compose.yml \
  root/asr_work/docker/docker-compose.yml \
  root/asr_work/holarasr_online/docker-compose.yml \
  root/apps/docker/holarfileparse/docker-compose.yml \
  data/aippt/docker-compose.yml \
  root/apps/docker/holarchat/docker-compose.yml \
  root/apps/docker/holarchatbi/docker-compose.yml \
  root/apps/docker/holargwxz/docker-compose.yml \
  root/apps/docker/holar2dhuman/docker-compose.yml \
  root/apps/docker/holarmeetnotesai/docker-compose.yml \
  root/work/holarvm/docker-compose.yml \
  opt/1panel/apps/local/holaros/holaros/docker-compose.yml \
  opt/1panel/apps/local/holarkanban/HolarKanban/docker-compose.yml \
  opt/1panel/apps/local/holartts/holartts/docker-compose.yml \
  opt/1panel/apps/local/windows-arm/windows-arm/docker-compose.yml ; do
  [ -f "$f" ] && FILES="$FILES $f"
  d=$(dirname "$f")
  [ -f "$d/.env" ] && FILES="$FILES $d/.env"
done
for s in root/scripts/create_network.sh root/scripts/start_all.sh root/scripts/stop_all.sh; do
  [ -f "$s" ] && FILES="$FILES $s"
done
tar czf /tmp/yamls_env_backup.tar.gz $FILES
echo "TAR_OK $(stat -c%s /tmp/yamls_env_backup.tar.gz) bytes, $(tar tzf /tmp/yamls_env_backup.tar.gz | wc -l) files"
echo "=== 文件清单 ==="
tar tzf /tmp/yamls_env_backup.tar.gz
