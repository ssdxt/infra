#!/bin/bash
sleep 15
echo "== ai_server: $(docker ps --format '{{.Names}} {{.Status}}' | grep '^ai_server ') =="
LOGIN=$(curl -s --max-time 15 -X POST http://localhost:8375/api/v1/auth/login -H 'Content-Type: application/json' -d '{"username":"su","password":"YWRtaW4xMjM="}')
TOKEN=$(echo "$LOGIN" | grep -oE '"token":"[^"]*"' | head -1 | cut -d'"' -f4)
echo "login: $(echo "$LOGIN" | head -c 60)..."
SPACE=9f7cf8c6-f866-4c58-9cb0-1ecd091c705c
UP=$(curl -s --max-time 20 -X PUT "http://localhost:8375/api/v1/spaces/$SPACE/images/upload" -H "Authorization: Bearer $TOKEN" -F 'image=@/tmp/t.png;type=image/png')
echo "upload: $(echo "$UP" | head -c 300)"
URL=$(echo "$UP" | grep -oE '"url":"[^"]*"' | head -1 | cut -d'"' -f4)
echo "URL: $URL"
if [ -n "$URL" ]; then
  echo '== 经 ngrok→nginx→minio 下载验证 =='
  curl -sk --max-time 30 -o /tmp/dl.png -w 'HTTP %{http_code} size %{size_download}\n' "$URL"
  head -c 8 /tmp/dl.png | xxd | head -1
fi
