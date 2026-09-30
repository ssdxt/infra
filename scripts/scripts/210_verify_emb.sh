#!/bin/bash
echo '== embedding /v1/models =='
docker exec ai_server curl -s --max-time 10 http://qwen-embedding:8021/v1/models 2>&1 | head -c 200
echo
echo '== real embedding call =='
docker exec ai_server curl -s --max-time 20 -X POST http://qwen-embedding:8021/v1/embeddings -H 'Content-Type: application/json' -d '{"model":"qwen-embedding","input":"你好，测试embedding"}' 2>&1 | head -c 300
echo
echo '== ai_server compose labels =='
docker inspect ai_server --format '{{json .Config.Labels}}' 2>/dev/null | tr ',' '\n' | grep -i compose
echo '== qwen refs in OmniKnow compose files =='
grep -nE 'qwen|embedding|rerank|8021|8022' /ManualAI/OmniKnow/docker-omniknow-fixed.yml /ManualAI/OmniKnow/docker-compose.yml 2>/dev/null | head -20
echo '== services in docker-omniknow-fixed.yml =='
grep -nE '^  [a-zA-Z0-9_-]+:' /ManualAI/OmniKnow/docker-omniknow-fixed.yml | head -30
