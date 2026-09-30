#!/bin/bash
echo '== 重建 server-api / celery（重新读 .env） =='
cd /ManualAI/OmniKnow
docker-compose -f docker-omniknow-fixed.yml up -d server-api celery-worker celery-beat 2>&1 | tail -6
sleep 20
echo '== 容器新 env 确认 =='
docker inspect ai_server --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | grep -E '^OSS_(SSL|WAN_HOST|WAN_PORT)'
echo '== 端到端测试 =='
TOKEN=$(curl -s --max-time 10 -X POST http://localhost:8375/api/v1/auth/login -H 'Content-Type: application/json' -d '{"username":"su","password":"YWRtaW4xMjM="}' | grep -oE '"token":"[^"]*"' | head -1 | cut -d'"' -f4)
SPACE=9f7cf8c6-f866-4c58-9cb0-1ecd091c705c
URL=$(curl -s --max-time 15 -X PUT "http://localhost:8375/api/v1/spaces/$SPACE/images/upload" -H "Authorization: Bearer $TOKEN" -F 'image=@/tmp/t.png;type=image/png' | grep -oE '"url":"[^"]*"' | head -1 | cut -d'"' -f4)
echo "返回 URL: $URL"
echo '== curl 该 URL（经 ngrok→nginx→minio）=='
curl -sk --max-time 25 -o /tmp/dl.png -w 'HTTP %{http_code} size %{size_download}\n' "$URL"
ls -la /tmp/dl.png 2>/dev/null
