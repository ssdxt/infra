#!/bin/bash
echo "== 8020 vLLM models =="
curl -s --max-time 10 http://127.0.0.1:8020/v1/models | head -c 300; echo

echo "== 8021 embeddings =="
EMB=$(curl -s --max-time 30 -X POST http://127.0.0.1:8021/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen-embedding","input":"hello 105"}')
echo "$EMB" | head -c 200; echo
echo "$EMB" | python3 -c "import sys,json; d=json.load(sys.stdin); print('embed_dim=', len(d['data'][0]['embedding']))" 2>&1

echo "== 8022 rerank =="
RR=$(curl -s --max-time 30 -X POST http://127.0.0.1:8022/v1/rerank \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen-rerank","query":"什么是液压系统","documents":["挖掘机液压系统原理","今天天气很好"]}')
echo "$RR" | head -c 300; echo

echo "== 8375 server-api health-ish =="
curl -s -o /dev/null -w 'backend root http=%{http_code}\n' --max-time 5 http://127.0.0.1:8375/
echo "== 8008 parser health =="
curl -s -o /dev/null -w 'parser health http=%{http_code}\n' --max-time 5 http://127.0.0.1:8008/health
