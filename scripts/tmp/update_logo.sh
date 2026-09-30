#!/bin/bash
# 重新预签名 kb 历史封面并写回 knowledge_base.logo
set -e

cat > /ManualAI/OmniKnow/omniknow2/re_sign.py <<'PYEOF'
import asyncio, sys
sys.path.insert(0, '/ManualAI/OmniKnow/omniknow2/server')
from storage.factory import build_storage_service
KEY = '1fc66f3c-31bd-4056-853d-0caadfb32369/images/2026/09/03/b361de030c714886.jpg'
async def main():
    svc = build_storage_service()
    url = await svc.presign_backend.presign(KEY, 604800)
    print(url)
asyncio.run(main())
PYEOF

URL=$(docker exec ai_server /root/anaconda3/envs/aiserver/bin/python /ManualAI/OmniKnow/omniknow2/re_sign.py)
rm -f /ManualAI/OmniKnow/omniknow2/re_sign.py
echo "NEW_URL=$URL"

CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$URL")
echo "VERIFY_HTTP=$CODE"

if [ "$CODE" = "200" ]; then
  ESC=$(printf '%s' "$URL" | sed "s/'/''/g")
  docker exec -i cc-mysql mysql -h 192.168.0.10 -uroot -pChicheng@1134 omniknow \
    -e "UPDATE knowledge_base SET logo='$ESC' WHERE uuid='29a2d90b9b434d56a67b44871a7d5cdf';" 2>&1 | grep -viE 'warning|insecure'
  echo "== verify db =="
  docker exec cc-mysql mysql -h 192.168.0.10 -uroot -pChicheng@1134 omniknow -N \
    -e "SELECT LEFT(logo,100) FROM knowledge_base WHERE uuid='29a2d90b9b434d56a67b44871a7d5cdf';" 2>/dev/null
else
  echo "SKIP DB update: verify not 200"
fi
