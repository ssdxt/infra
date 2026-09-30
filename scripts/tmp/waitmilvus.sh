#!/bin/bash
echo "== wait milvus 9091 =="
ok=""
for i in $(seq 1 48); do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "http://127.0.0.1:9091/healthz" 2>/dev/null)
  if [ "$code" = "200" ]; then echo "milvus READY (${i}x10s)"; ok=1; break; fi
  sleep 10
done
[ -z "$ok" ] && echo "milvus NOT-READY (timeout)"

echo "== wait parser 8008 =="
ok=""
for i in $(seq 1 24); do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "http://127.0.0.1:8008/health" 2>/dev/null)
  if [ "$code" = "200" ]; then echo "parser READY (${i}x10s)"; ok=1; break; fi
  sleep 10
done
[ -z "$ok" ] && echo "parser NOT-READY (timeout)"

echo "== final status =="
docker ps --format '{{.Names}} | {{.Status}}' | grep -E 'qwen|parser|mineru|milvus|ai_server|assistant|ai_mysql|ai_redis|ai_minio|ai_nginx' | sort
