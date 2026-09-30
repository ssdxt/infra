#!/bin/bash
echo "== 镜像内 transcribe 定义 =="
docker exec ai_server_backend grep -rn "audio/transcribe\|def transcribe" /app --include="*.py" 2>/dev/null | head -10
echo "== 相关路由文件内容 =="
f=$(docker exec ai_server_backend sh -c 'grep -rln "audio/transcribe" /app --include="*.py" 2>/dev/null | head -1')
echo "FILE=$f"
[ -n "$f" ] && docker exec ai_server_backend cat "$f" | head -60
