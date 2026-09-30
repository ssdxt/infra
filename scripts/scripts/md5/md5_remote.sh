#!/bin/bash
cd /
md5sum \
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
  opt/1panel/apps/local/windows-arm/windows-arm/docker-compose.yml
