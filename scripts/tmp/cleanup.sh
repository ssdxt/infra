#!/bin/bash
# 删除上传验证的测试残留 test.pdf
BASE="http://127.0.0.1:8378/backend/api/v1"
B64=$(printf '%s' 'admin123' | base64)
LOGIN=$(curl -s -X POST "$BASE/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"admin\",\"password\":\"$B64\"}")
TOKEN=$(echo "$LOGIN" | grep -oE '"(token|access_token)":"[^"]+"' | head -1 | sed 's/.*":"//;s/"//')
AUTH="Authorization: Bearer $TOKEN"
SPACE=1fc66f3c-31bd-4056-853d-0caadfb32369
KB=29a2d90b-9b43-4d56-a67b-44871a7d5cdf
DOC=e0c75f17-ea34-4e20-b1ea-9bb826b76cab
echo "== DELETE test.pdf resource =="
curl -s -X DELETE "$BASE/spaces/$SPACE/kbs/$KB/resources/$DOC" -H "$AUTH" | head -c 300; echo
echo "== GET docs after cleanup =="
curl -s "$BASE/spaces/$SPACE/kbs/$KB/docs" -H "$AUTH" | head -c 300; echo
