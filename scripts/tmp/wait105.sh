#!/bin/bash
# 轮询 105 各推理服务健康，最长 ~6 分钟
for p in 8020 8021 8022; do
  ok=""
  for i in $(seq 1 36); do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "http://127.0.0.1:$p/health" 2>/dev/null)
    if [ "$code" = "200" ]; then echo "port $p READY (${i}x10s)"; ok=1; break; fi
    sleep 10
  done
  [ -z "$ok" ] && echo "port $p NOT-READY (timeout)"
done
echo "=== final probe ==="
for p in 8008 8000 8375 8366; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 "http://127.0.0.1:$p/" 2>/dev/null)
  echo "port $p => ${code:-NO}"
done
