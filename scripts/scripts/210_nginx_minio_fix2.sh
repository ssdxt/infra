#!/bin/bash
CONF=/ManualAI/OmniKnow/data/nginx/subconf/omniknow.conf
echo '== 恢复干净配置 =='
cp "$CONF.bak.awk" "$CONF"
cat > /tmp/minio_block.txt <<'EOF'
        # MinIO 对象存储同源代理（bucket 路径 -> minio:9000）
        location ~ "^/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/(images|logo|documents|processed|chunks|media|source)/" {
            proxy_pass http://minio:9000;
            proxy_set_header Host $host;
        }
        location ~ "^/(public|ccaibucket)/" {
            proxy_pass http://minio:9000;
            proxy_set_header Host $host;
        }

EOF
awk 'NR==FNR { block = block $0 "\n"; next }
     { if (!done && index($0, "location  / {") > 0) { printf "%s", block; done = 1 }
       print }' /tmp/minio_block.txt "$CONF" > "$CONF.tmp" && mv "$CONF.tmp" "$CONF"
echo '== nginx 校验重载 =='
docker exec cc-nginx nginx -t 2>&1 | tail -2
docker exec cc-nginx nginx -s reload 2>&1 && echo reloaded
sleep 2
echo '== bucket 路径直测 =='
curl -s -o /dev/null -w '无签名 bucket 路径 => %{http_code} (%{content_type})\n' --max-time 10 "http://localhost:8378/9f7cf8c6-f866-4c58-9cb0-1ecd091c705c/images/2026/09/03/adb5fc9c83f04f8e.png"
echo '== 带签名 URL 全链路下载 =='
URL="https://snowsuit-swirl-sporty.ngrok-free.dev:443/9f7cf8c6-f866-4c58-9cb0-1ecd091c705c/images/2026/09/03/adb5fc9c83f04f8e.png"
curl -sk --max-time 30 -o /tmp/dl2.png -w '下载 => HTTP %{http_code} size %{size_download}\n' "$URL"
head -c 4 /tmp/dl2.png | xxd | head -1
