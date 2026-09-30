#!/bin/bash
echo '== compose binary =='
docker compose version 2>&1 | head -1
docker-compose version 2>&1 | head -1
echo '== compose services =='
grep -nE '^  [a-z_0-9-]+:' /ManualAI/docker-compose.yml | head -40
echo '== qwen-embedding section =='
awk '/^  qwen-embedding:/,/^  [a-z_0-9-]+:/' /ManualAI/docker-compose.yml | head -60
echo '== current container compose labels =='
docker inspect qwen-embedding --format '{{json .Config.Labels}}' 2>/dev/null | tr ',' '\n' | grep -i compose
echo '== rerank section (device part only) =='
awk '/^  qwen-rerank:/,/^  [a-z_0-9-]+:/' /ManualAI/docker-compose.yml | grep -nE 'CUDA|NVIDIA|devices|runtime|image|gpus' | head -10
echo '== script GPU line =='
grep -n 'CUDA_VISIBLE_DEVICES' /ManualAI/OmniKnow/bash/start_qwen_embedding_06b.sh
