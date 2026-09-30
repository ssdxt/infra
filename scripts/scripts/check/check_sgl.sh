#!/bin/bash
echo "=== sgl_1.2b 崩溃日志 (tail 25) ==="
docker logs holarfileparse_sgl_1.2b --tail 25 2>&1 | tail -25
echo
echo "=== GPU 显存现状 ==="
nvidia-smi 2>/dev/null | grep -E 'MiB|%' | head -15
echo
echo "=== GPU 上正在跑的进程 ==="
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader 2>/dev/null | head -10
echo
echo "=== one-api 端口与日志 ==="
docker port one-api 2>/dev/null
curl -s -o /dev/null -w "one-api /login -> %{http_code}\n" --connect-timeout 3 -m 5 http://192.168.21.105:2300/login 2>/dev/null
docker logs one-api --tail 5 2>&1 | tail -5
