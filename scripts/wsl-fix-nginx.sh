#!/bin/bash
# 访问 Harbor 不走代理；访问 docker.io 走 WSL 的代理
export NO_PROXY='harbor.wuxing.local,10.100.10.29,localhost,127.0.0.1'
export no_proxy="$NO_PROXY"
echo "=== 环境确认 ==="
echo "  HTTPS_PROXY=${HTTPS_PROXY:-未设置}"
echo "  NO_PROXY=$NO_PROXY"
echo ""
echo "=== 修复前：nginx:latest 的架构 ==="
skopeo inspect --raw --tls-verify=false --creds admin:'<HARBOR_PASSWORD>' docker://harbor.wuxing.local/library/nginx:latest 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); print("  mediaType:", d.get("mediaType","?")); [print("   平台:", (m.get("platform") or {}).get("os"), (m.get("platform") or {}).get("architecture")) for m in d.get("manifests",[])] or print("   -> 单架构 manifest（无 manifests 字段）")'
echo ""
echo "=== 执行多架构复制（--multi-arch all） ==="
time skopeo copy --multi-arch all \
  --dest-tls-verify=false \
  --dest-creds admin:'<HARBOR_PASSWORD>' \
  docker://docker.io/library/nginx:latest \
  docker://harbor.wuxing.local/library/nginx:latest 2>&1 | tail -8
echo ""
echo "=== 修复后：nginx:latest 的架构 ==="
skopeo inspect --raw --tls-verify=false --creds admin:'<HARBOR_PASSWORD>' docker://harbor.wuxing.local/library/nginx:latest 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); print("  mediaType:", d.get("mediaType","?")); [print("   平台:", (m.get("platform") or {}).get("os"), "/", (m.get("platform") or {}).get("architecture")) for m in d.get("manifests",[])]'