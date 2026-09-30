#!/bin/bash
echo "== ai_server 镜像内 transcribe 路由定义 =="
docker exec ai_server grep -rn "audio/transcribe" /app --include="*.py" 2>/dev/null | head -8
echo "== ai_server 内路由文件 =="
docker exec ai_server sh -c 'grep -rn "transcribe" /app/api /app/shared /app/routers 2>/dev/null | grep -i route | head -5'
echo "== nginx access log 最近 transcribe =="
grep -h "audio/transcribe" /ManualAI/depends_on/data/nginx/logs/*.log 2>/dev/null | tail -5
echo "== 前端 js 中 transcribe 调用 =="
f=$(grep -rl "audio/transcribe" /ManualAI/depends_on/data/nginx/html/omniknow/assets/ 2>/dev/null | head -1)
echo "FILE=$f"
grep -oE '.{120}audio/transcribe.{60}' "$f" 2>/dev/null | head -2
