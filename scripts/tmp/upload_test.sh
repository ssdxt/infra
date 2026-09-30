#!/bin/bash
# kb 页面上传链路验证：登录 -> 上传图片 -> 验证返回 URL 可访问
B64=$(printf '%s' 'admin123' | base64)
echo "== login =="
LOGIN=$(curl -s -X POST http://127.0.0.1:8375/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"admin\",\"password\":\"$B64\"}")
echo "$LOGIN" | head -c 400; echo
TOKEN=$(echo "$LOGIN" | grep -oE '"(token|access_token)":"[^"]+"' | head -1 | sed 's/.*":"//;s/"//')
echo "TOKEN_PREFIX=${TOKEN:0:16}..."

SPACE=1fc66f3c-31bd-4056-853d-0caadfb32369
IMG=/ManualAI/OmniKnow/omniknow2/assistant/src/graph_neo.png

echo "== upload image =="
UP=$(curl -s -X PUT "http://127.0.0.1:8375/api/v1/spaces/$SPACE/images/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "image=@$IMG" -F "expire=3600")
echo "$UP" | head -c 800; echo
URL=$(echo "$UP" | grep -oE 'https?://[^"]+' | head -1)
echo "URL=$URL"

echo "== verify URL =="
if [ -n "$URL" ]; then
  CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 25 "$URL")
  echo "HTTP=$CODE"
fi
