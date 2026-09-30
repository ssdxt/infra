#!/bin/bash
export NO_PROXY='harbor.wuxing.local,10.100.10.29,localhost,127.0.0.1'
export no_proxy="$NO_PROXY"
H=harbor.wuxing.local
CREDS="admin:<HARBOR_PASSWORD>"
R=$H/library/exp-c

# 关键：把 Harbor CA 合并进系统 CA 包，让 Go 系工具（regctl）信任自签证书
cat /etc/ssl/certs/ca-certificates.crt "/mnt/c/Users/CC/Desktop/dsh/harbor-ca.crt" > /tmp/ca-bundle.crt 2>/dev/null
export SSL_CERT_FILE=/tmp/ca-bundle.crt
echo "  SSL_CERT_FILE=$SSL_CERT_FILE ($(wc -l < /tmp/ca-bundle.crt) 行)"

echo ""
echo "===== 1. 验证 regctl 现在能否信任 Harbor ====="
regctl registry set $H --tls enabled >/dev/null 2>&1
regctl registry login $H -u admin -p "$CREDS" 2>&1 | tail -1
regctl repo ls $H 2>&1 | head -3 && echo "  ✓ regctl 可访问 Harbor" || echo "  ✗ 仍失败"

echo ""
echo "===== 2. 用 regctl index create 组装「恰好 amd64+arm64」====="
regctl index create "$R:latest" \
  --ref "$R:amd64" \
  --ref "$R:arm64" 2>&1 | tail -3
echo ""
echo "--- 组装结果:"
skopeo inspect --raw --tls-verify=false --creds "$CREDS" "docker://$R:latest" 2>/dev/null | python3 -c '
import sys,json
try: d=json.load(sys.stdin)
except Exception: print("    (不存在)"); raise SystemExit
if "manifests" not in d: print("    单架构")
else:
    p=[]
    for m in d["manifests"]:
        pl=m.get("platform") or {}
        a=pl.get("architecture")
        if a and a!="unknown": p.append(pl.get("os","?")+"/"+a)
    print("    mediaType:", d.get("mediaType"))
    print("    ✓ 架构数:", len(p), sorted(set(p)))
'

echo ""
echo "===== 3. 清理 exp-c 的临时 tag ====="
for t in amd64 arm64; do
  d=$(curl -sk -u "$CREDS" -o /dev/null -D - -H 'Accept: application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json' "https://$H/v2/library/exp-c/manifests/$t" 2>/dev/null | grep -i '^docker-content-digest' | tr -d '\r' | awk '{print $2}')
  [ -n "$d" ] && echo "  删 $t -> HTTP $(curl -sk -u "$CREDS" -o /dev/null -w '%{http_code}' -X DELETE "https://$H/v2/library/exp-c/manifests/$d")"
done
echo -n "  剩余 tag: "; curl -sk -u "$CREDS" "https://$H/v2/library/exp-c/tags/list" 2>/dev/null; echo
