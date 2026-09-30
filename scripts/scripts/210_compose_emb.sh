#!/bin/bash
echo '== before edit (embedding env) =='
sed -n '10,16p' /ManualAI/OmniKnow/docker-omniknow-fixed.yml
sed -i -e '/^  qwen-embedding:/,/^  qwen-rerank:/ s/NVIDIA_VISIBLE_DEVICES: "1"/NVIDIA_VISIBLE_DEVICES: "0"/' \
       -e '/^  qwen-embedding:/,/^  qwen-rerank:/ s/CUDA_VISIBLE_DEVICES: "1"/CUDA_VISIBLE_DEVICES: "0"/' \
       /ManualAI/OmniKnow/docker-omniknow-fixed.yml
echo '== after edit =='
sed -n '10,16p' /ManualAI/OmniKnow/docker-omniknow-fixed.yml
echo '== compose up qwen-embedding =='
cd /ManualAI/OmniKnow && docker-compose -f docker-omniknow-fixed.yml up -d qwen-embedding 2>&1 | tail -6
sleep 45
echo '== status =='
docker ps --format '{{.Names}} | {{.Status}}' | grep qwen
echo '== compose labels =='
docker inspect qwen-embedding --format '{{json .Config.Labels}}' 2>/dev/null | tr ',' '\n' | grep -i compose | head -4
echo '== api test =='
docker exec ai_server curl -s --max-time 15 -X POST http://qwen-embedding:8021/v1/embeddings -H 'Content-Type: application/json' -d '{"model":"qwen-embedding","input":"compose 管理测试"}' 2>&1 | head -c 200
