#!/bin/bash
# kb 页面文件链路验证：经 nginx /backend/ 反代路径（等同浏览器）
BASE="http://127.0.0.1:8378/backend/api/v1"
B64=$(printf '%s' 'admin123' | base64)

echo "== login via nginx /backend/ =="
LOGIN=$(curl -s -X POST "$BASE/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"admin\",\"password\":\"$B64\"}")
echo "$LOGIN" | head -c 200; echo
TOKEN=$(echo "$LOGIN" | grep -oE '"(token|access_token)":"[^"]+"' | head -1 | sed 's/.*":"//;s/"//')
echo "TOKEN_PREFIX=${TOKEN:0:16}..."
AUTH="Authorization: Bearer $TOKEN"

SPACE=1fc66f3c-31bd-4056-853d-0caadfb32369
KB=29a2d90b-9b43-4d56-a67b-44871a7d5cdf
PDF=/ManualAI/OmniKnow/omniknow2/parser/rag/parser/test_case/test.pdf

echo "== GET docs (list) =="
curl -s "$BASE/spaces/$SPACE/kbs/$KB/docs" -H "$AUTH" | head -c 600; echo

echo "== GET resources (list) =="
curl -s "$BASE/spaces/$SPACE/kbs/$KB/resources" -H "$AUTH" | head -c 600; echo

echo "== POST docs/upload =="
UP=$(curl -s -X POST "$BASE/spaces/$SPACE/kbs/$KB/docs/upload" \
  -H "$AUTH" -F "files=@$PDF")
echo "$UP" | head -c 900; echo
