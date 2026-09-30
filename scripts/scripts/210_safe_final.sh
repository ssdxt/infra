#!/bin/bash
echo '== 加 ENV_SAFE=1 =='
grep -q '^ENV_SAFE=' /ManualAI/OmniKnow/omniknow2/server/.env && sed -i 's|^ENV_SAFE=.*|ENV_SAFE=1|' /ManualAI/OmniKnow/omniknow2/server/.env || echo 'ENV_SAFE=1' >> /ManualAI/OmniKnow/omniknow2/server/.env
grep -n '^ENV_SAFE=' /ManualAI/OmniKnow/omniknow2/server/.env
echo '== 重建 ai_server =='
cd /ManualAI/OmniKnow
docker-compose -f docker-omniknow-fixed.yml up -d server-api 2>&1 | tail -2
sleep 25
docker ps --format '{{.Names}} | {{.Status}}' | grep '^ai_server '
echo '== 全链路测试 =='
LOGIN=$(curl -s --max-time 15 -X POST http://localhost:8375/api/v1/auth/login -H 'Content-Type: application/json' -d '{"username":"su","password":"YWRtaW4xMjM="}')
TOKEN=$(echo "$LOGIN" | grep -oE '"token":"[^"]*"' | head -1 | cut -d'"' -f4)
SPACE=9f7cf8c6-f866-4c58-9cb0-1ecd091c705c
UP=$(curl -s --max-time 20 -X PUT "http://localhost:8375/api/v1/spaces/$SPACE/images/upload" -H "Authorization: Bearer $TOKEN" -F 'image=@/tmp/t.png;type=image/png')
echo "upload: $(echo "$UP" | head -c 400)"
URL=$(echo "$UP" | grep -oE '"url":"[^"]*"' | head -1 | cut -d'"' -f4)
echo '== 下载验证 =='
curl -sk --max-time 30 -o /tmp/final.png -w 'HTTP %{http_code} size %{size_download}\n' "$URL"
head -c 4 /tmp/final.png | xxd | head -1
