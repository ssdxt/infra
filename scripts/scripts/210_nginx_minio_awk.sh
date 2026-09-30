#!/bin/bash
CONF=/ManualAI/OmniKnow/data/nginx/subconf/omniknow.conf
cat > /tmp/minio_block.txt <<'EOF'
        # MinIO 对象存储同源代理（bucket 路径 -> minio:9000）
        location ~ ^/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/(images|logo|documents|processed|chunks|media|source)/ {
            proxy_pass http://minio:9000;
            proxy_set_header Host $host;
        }
        location ~ ^/(public|ccaibucket)/ {
            proxy_pass http://minio:9000;
            proxy_set_header Host $host;
        }

EOF
cp "$CONF" "$CONF.bak.awk"
awk 'NR==FNR { block = block $0 "\n"; next }
     { if (!done && index($0, "location  / {") > 0) { printf "%s", block; done = 1 }
       print }' /tmp/minio_block.txt "$CONF" > "$CONF.tmp" && mv "$CONF.tmp" "$CONF"
echo '== 插入结果 =='
grep -n 'minio\|location ~' "$CONF" | head -8
echo '== nginx 校验重载 =='
docker exec cc-nginx nginx -t 2>&1 | tail -2
docker exec cc-nginx nginx -s reload 2>&1 && echo reloaded
sleep 2
echo '== 直接验证 bucket 路径是否走 minio =='
curl -s -o /dev/null -w 'bucket 路径 => %{http_code} (%{content_type})\n' --max-time 10 "http://localhost:8378/9f7cf8c6-f866-4c58-9cb0-1ecd091c705c/images/2026/09/03/adb5fc9c83f04f8e.png"
