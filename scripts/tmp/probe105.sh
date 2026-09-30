#!/bin/bash
docker ps --format '{{.Names}} | {{.Status}}' | grep -E 'assistant|ai_server|ai_mysql|milvus|ai_redis|ai_minio|ai_nginx'
echo "=== PROBE ==="
for p in 8375 8366; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:$p/ 2>/dev/null)
  echo "port $p => ${code:-NO}"
done
