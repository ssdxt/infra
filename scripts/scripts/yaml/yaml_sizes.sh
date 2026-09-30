#!/bin/bash
for f in \
  /root/apps/docker/holarfileparse/docker-compose.yml \
  /root/sherpa/docker/docker-compose.yml \
  /root/embed/docker-compose-embed.yml \
  /root/llm/docker_2/mineru_2509_1.2b/docker-compose.yml \
  /root/asr_work/holarasr_online/docker-compose.yml \
  /root/asr_work/docker/docker-compose.yml \
  /data/aippt/docker-compose.yml \
  /root/apps/docker/holarchat/docker-compose.yml \
  /opt/1panel/apps/local/holaros/holaros/docker-compose.yml \
  /root/work/holarvm/docker-compose.yml \
  /root/work/docker-compose-deepdoc.yml \
  /opt/1panel/apps/local/holarkanban/HolarKanban/docker-compose.yml \
  /root/work/docker-compose-oneapi.yml \
  /opt/1panel/apps/local/holartts/holartts/docker-compose.yml \
  /root/work/docker-compose-database.yaml ; do
  if [ -f "$f" ]; then
    echo "###### FILE: $f ($(wc -l < "$f") lines)"
  else
    echo "###### FILE MISSING: $f"
  fi
done
