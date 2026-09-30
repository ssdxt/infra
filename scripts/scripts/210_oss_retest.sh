#!/bin/bash
sleep 15
echo '== ai_server 状态 =='
docker ps --format '{{.Names}} | {{.Status}}' | grep ai_server
echo '== 登录原始响应 =='
LOGIN=$(curl -s --max-time 15 -X POST http://localhost:8375/api/v1/auth/login -H 'Content-Type: application/json' -d '{"username":"su","password":"YWRtaW4xMjM="}')
echo "$LOGIN" | head -c 200
echo
TOKEN=$(echo "$LOGIN" | grep -oE '"token":"[^"]*"' | head -1 | cut -d'"' -f4)
echo "token: ${TOKEN:0:15}..."
SPACE=9f7cf8c6-f866-4c58-9cb0-1ecd091c705c
echo '== 上传原始响应 =='
UP=$(curl -s --max-time 20 -X PUT "http://localhost:8375/api/v1/spaces/$SPACE/images/upload" -H "Authorization: Bearer $TOKEN" -F 'image=@/tmp/t.png;type=image/png')
echo "$UP" | head -c 500
echo
URL=$(echo "$UP" | grep -oE '"url":"[^"]*"' | head -1 | cut -d'"' -f4)
echo "URL: $URL"
if [ -n "$URL" ]; then
  curl -sk --max-time 25 -o /tmp/dl.png -w '下载: HTTP %{http_code} size %{size_download}\n' "$URL"
fi
