#!/bin/bash
TOKEN=$(curl -s --max-time 10 -X POST http://localhost:8375/api/v1/auth/login -H 'Content-Type: application/json' -d '{"username":"su","password":"YWRtaW4xMjM="}' | grep -oE '"token":"[^"]*"' | head -1 | cut -d'"' -f4)
SPACE=9f7cf8c6-f866-4c58-9cb0-1ecd091c705c
echo '== 图片上传(image 字段) =='
curl -s --max-time 15 -X PUT "http://localhost:8375/api/v1/spaces/$SPACE/images/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F 'image=@/tmp/t.png;type=image/png' | head -c 500
echo
echo '== 日志确认 =='
tail -6 /ManualAI/OmniKnow/logs/aiserver.log 2>/dev/null | grep -E 'images/upload|ERROR|bucket' | head -3
