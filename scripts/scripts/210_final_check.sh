#!/bin/bash
echo '== embedding compose labels =='
docker inspect qwen-embedding --format '{{json .Config.Labels}}' 2>/dev/null | tr ',' '\n' | grep -iE 'compose.(project|service|config_files)' | head -4
echo '== rerank compose labels =='
docker inspect qwen-rerank --format '{{json .Config.Labels}}' 2>/dev/null | tr ',' '\n' | grep -iE 'compose.(project|service)' | head -3
echo '== embedding dim check =='
docker exec ai_server curl -s --max-time 20 -X POST http://qwen-embedding:8021/v1/embeddings -H 'Content-Type: application/json' -d '{"model":"qwen-embedding","input":"测试维度"}' 2>&1 | python -c "import sys,json; d=json.load(sys.stdin); print('dim:', len(d['data'][0]['embedding']))" 2>&1
echo '== rerank functional test =='
docker exec ai_server curl -s --max-time 25 -X POST http://qwen-rerank:8022/v1/rerank -H 'Content-Type: application/json' -d '{"model":"qwen-rerank","query":"今天天气怎么样","documents":["今天天气很好适合出行","苹果是一种水果"]}' 2>&1 | head -c 300
echo
echo '== GPU usage =='
nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv,noheader
