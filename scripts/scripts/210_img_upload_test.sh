#!/bin/bash
TOKEN=$(curl -s --max-time 10 -X POST http://localhost:8375/api/v1/auth/login -H 'Content-Type: application/json' -d '{"username":"su","password":"YWRtaW4xMjM="}' | grep -oE '"token":"[^"]*"' | head -1 | cut -d'"' -f4)
echo "token: ${TOKEN:0:20}..."
SPACE=9f7cf8c6-f866-4c58-9cb0-1ecd091c705c
echo 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==' | base64 -d > /tmp/t.png
echo '== 图片上传 =='
curl -s --max-time 15 -X PUT "http://localhost:8375/api/v1/spaces/$SPACE/images/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F 'file=@/tmp/t.png;type=image/png' | head -c 400
echo
echo '== ai_server 日志最近相关 =='
tail -8 /ManualAI/OmniKnow/logs/aiserver.log 2>/dev/null | grep -E 'image|bucket|ERROR|NoSuch' | head -5
