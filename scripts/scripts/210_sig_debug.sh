#!/bin/bash
URL="https://snowsuit-swirl-sporty.ngrok-free.dev:443/9f7cf8c6-f866-4c58-9cb0-1ecd091c705c/images/2026/09/03/adb5fc9c83f04f8e.png"
echo '== 403 XML 内容 =='
curl -sk --max-time 20 "$URL" | head -c 500
echo
echo '== 同签名直连 minio（换 host 为内网） =='
DIRECT=$(echo "$URL" | sed 's|https://snowsuit-swirl-sporty.ngrok-free.dev:443|http://localhost:9000|')
curl -s --max-time 20 -o /tmp/dl3.png -w '直连 => HTTP %{http_code} size %{size_download}\n' "$DIRECT"
head -c 300 /tmp/dl3.png 2>/dev/null | head -c 300
echo
echo '== 各容器时钟 =='
for c in ai_server minio cc-nginx; do echo -n "$c: "; docker exec $c date '+%F %T %z' 2>/dev/null || docker exec $c sh -c date '+%F %T %z' 2>/dev/null; done
date '+host: %F %T %z'
