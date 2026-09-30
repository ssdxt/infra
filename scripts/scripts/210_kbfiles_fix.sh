#!/bin/bash
F=/ManualAI/OmniKnow/omniknow2/assistant/src/tools/kb_files.py
E=/ManualAI/OmniKnow/omniknow2/assistant/.env
cp "$F" "$F.bak.$(date +%H%M%S)"
sed -i 's|"http://192.168.0.23:8375"|"http://ai_server:8375"|' "$F"
echo '== 代码修改确认 =='
grep -n 'DEFAULT_KB_API_BASE_URL' "$F" | head -2
docker exec assistant /root/anaconda3/bin/python -c "import ast; ast.parse(open('$F', encoding='utf-8').read()); print('syntax OK')"

echo '== assistant/.env 追加 env 覆盖 + ngrok 来源 =='
grep -q '^KB_RESOURCES_API_BASE_URL' "$E" || echo 'KB_RESOURCES_API_BASE_URL=http://ai_server:8375' >> "$E"
grep -q 'snowsuit-swirl-sporty.ngrok-free.dev' "$E" || sed -i 's|^ALLOWED_ORIGINS=.*|ALLOWED_ORIGINS="http://127.0.0.1:8378,http://183.129.232.94:18376,https://snowsuit-swirl-sporty.ngrok-free.dev"|' "$E"
grep -nE 'KB_RESOURCES_API_BASE_URL|ALLOWED_ORIGINS' "$E"

echo '== 重建 assistant =='
cd /ManualAI/OmniKnow
docker-compose -f docker-omniknow-fixed.yml up -d assistant 2>&1 | tail -2
sleep 18
docker ps --format '{{.Names}} | {{.Status}}' | grep assistant
echo '== assistant 环境确认 =='
docker exec assistant sh -c 'tr "\0" "\n" < /proc/1/environ' 2>/dev/null | grep -E 'KB_RESOURCES_API_BASE_URL|ALLOWED_ORIGINS' | head -3
echo '== assistant -> ai_server 连通性 =='
docker exec assistant curl -s -o /dev/null -w 'ai_server:8375 => %{http_code}\n' --max-time 8 http://ai_server:8375/ 2>&1 | tail -1
