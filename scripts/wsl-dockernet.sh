#!/bin/bash
export no_proxy='10.100.10.0/24,harbor.wuxing.local'
export NO_PROXY='10.100.10.0/24,harbor.wuxing.local'
echo "== docker daemon 网络到 harbor"
docker run --rm --network host alpine:3.20 sh -c 'wget -q -O- --timeout=8 http://10.100.10.29 2>&1 | head -c 100; echo; wget -q --timeout=8 https://10.100.10.29 -O /dev/null 2>&1 && echo https-ok || echo https-fail' 2>&1 | head -5
echo "== 直接从 WSL 用户态 docker login（带 --config 指定空代理）"
docker logout harbor.wuxing.local 2>/dev/null
echo "$HP" | docker login harbor.wuxing.local -u admin --password-stdin 2>&1 | tail -2