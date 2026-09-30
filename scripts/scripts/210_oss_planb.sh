#!/bin/bash
TS=$(date +%H%M%S)
ENVF=/ManualAI/OmniKnow/omniknow2/server/.env
CONF=/ManualAI/OmniKnow/data/nginx/subconf/omniknow.conf
DOMAIN=snowsuit-swirl-sporty.ngrok-free.dev

echo '== 1. 改 server/.env =='
cp "$ENVF" "$ENVF.bak.$TS"
sed -i 's|^OSS_SSL=.*|OSS_SSL=1|' "$ENVF"
sed -i "s|^OSS_WAN_HOST=.*|OSS_WAN_HOST=$DOMAIN|" "$ENVF"
sed -i 's|^OSS_WAN_PORT=.*|OSS_WAN_PORT=443|' "$ENVF"
grep -nE '^OSS_(SSL|WAN_HOST|WAN_PORT|HOST|PORT)=' "$ENVF"

echo '== 2. nginx 加 minio 同源代理 =='
cp "$CONF" "$CONF.bak.$TS"
python2 - <<PYEOF
p = '$CONF'
s = open(p).read()
anchor = '        location  / {'
assert s.count(anchor) == 1
block = '''        # MinIO 对象存储同源代理（bucket 路径 -> minio:9000）
        location ~ ^/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/(images|logo|documents|processed|chunks|media|source)/ {
            proxy_pass http://minio:9000;
            proxy_set_header Host \$host;
        }
        location ~ ^/(public|ccaibucket)/ {
            proxy_pass http://minio:9000;
            proxy_set_header Host \$host;
        }

'''
s = s.replace(anchor, block + anchor)
open(p, 'wb').write(s.encode('utf-8'))
print('nginx conf patched')
PYEOF

echo '== 3. reload nginx =='
docker exec cc-nginx nginx -t 2>&1 | tail -2
docker exec cc-nginx nginx -s reload 2>&1 && echo 'reloaded'

echo '== 4. 重启 ai_server =='
docker restart ai_server 2>&1
sleep 12

echo '== 5. 端到端验证：登录→传图→抓返回URL→curl验证 =='
TOKEN=$(curl -s --max-time 10 -X POST http://localhost:8375/api/v1/auth/login -H 'Content-Type: application/json' -d '{"username":"su","password":"YWRtaW4xMjM="}' | grep -oE '"token":"[^"]*"' | head -1 | cut -d'"' -f4)
SPACE=9f7cf8c6-f866-4c58-9cb0-1ecd091c705c
URL=$(curl -s --max-time 15 -X PUT "http://localhost:8375/api/v1/spaces/$SPACE/images/upload" -H "Authorization: Bearer $TOKEN" -F 'image=@/tmp/t.png;type=image/png' | grep -oE '"url":"[^"]*"' | head -1 | cut -d'"' -f4)
echo "返回 URL: $URL"
echo "== curl 该 URL（经 ngrok→nginx→minio）=="
curl -sk --max-time 20 -o /tmp/dl.png -w 'HTTP %{http_code} size %{size_download}\n' "$URL"
file /tmp/dl.png 2>/dev/null || ls -la /tmp/dl.png
