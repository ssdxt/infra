#!/bin/bash
echo "== before =="
df -h / | tail -1
echo "== deleting dockerimage tars =="
rm -rf /ManualAI/dockerimages/*.tar
ls /ManualAI/dockerimages/ 2>/dev/null | head
echo "== after =="
df -h / | tail -1
echo "== test image URL from error.log (b361de, in sig validity) =="
URL=$(grep -hoE 'http[^ ]*b361de030c714886\.jpg[^ ]*' /ManualAI/OmniKnow/data/nginx/logs/error.log 2>/dev/null | head -1)
echo "TEST_URL=$URL"
if [ -n "$URL" ]; then
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$URL")
  echo "image-http=$code"
fi
echo "== test upload new image =="
B64=$(printf '%s' 'admin123' | base64)
LOGIN=$(curl -s -X POST http://127.0.0.1:8375/api/v1/auth/login -H 'Content-Type: application/json' -d "{\"username\":\"admin\",\"password\":\"$B64\"}")
TOKEN=$(echo "$LOGIN" | grep -oE '"(token|access_token)":"[^"]+"' | head -1 | sed 's/.*":"//;s/"//')
SPACE=1fc66f3c-31bd-4056-853d-0caadfb32369
UP=$(curl -s -X PUT "http://127.0.0.1:8375/api/v1/spaces/$SPACE/images/upload" -H "Authorization: Bearer $TOKEN" -F image=@/ManualAI/OmniKnow/omniknow2/assistant/src/graph_neo.png -F expire=3600)
echo "$UP" | head -c 200; echo
NURL=$(echo "$UP" | grep -oE 'https?://[^"]+' | head -1)
echo "new-url=$NURL"
if [ -n "$NURL" ]; then
  code2=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$NURL")
  echo "new-image-http=$code2"
fi
