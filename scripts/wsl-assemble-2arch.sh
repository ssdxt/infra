#!/bin/bash
# 目标：可靠地做出"恰好 linux/amd64 + linux/arm64"两个架构、单一 tag 的镜像
# 方法：skopeo 分别推两个单架构到临时 tag → regctl 组装 index → 删临时 tag
export NO_PROXY='harbor.wuxing.local,10.100.10.29,localhost,127.0.0.1'
export no_proxy="$NO_PROXY"
H=harbor.wuxing.local
CREDS="admin:<HARBOR_PASSWORD>"

show() {
  echo "--- $2"
  skopeo inspect --raw --tls-verify=false --creds "$CREDS" "docker://$1" 2>/dev/null | python3 -c '
import sys, json
try: d = json.load(sys.stdin)
except Exception: print("    (读取失败/不存在)"); raise SystemExit
if "manifests" not in d:
    print("    mediaType:", d.get("mediaType"), "-> 单架构")
    print("    config:", (d.get("config") or {}).get("mediaType",""))
else:
    print("    mediaType:", d.get("mediaType"))
    p=[]
    for m in d["manifests"]:
        pl=m.get("platform") or {}
        a=pl.get("architecture")
        if a and a!="unknown": p.append(pl.get("os","?")+"/"+a+("/"+pl["variant"] if pl.get("variant") else ""))
    print("    -> 架构数:", len(p), sorted(set(p)))
'
}

REPO=monitoring/prometheus
TAG=v2.54.1
SRC=docker.io/quay.io/prometheus/prometheus:$TAG

echo "===== 0. regctl 组装能力检查 ====="
regctl image index create --help 2>&1 | grep -E '^\s+--ref|Usage|create a new' | head -5
echo ""

echo "===== 1. 配置 regctl（自签证书 + 认证）====="
regctl registry set --tls disabled harbor.wuxing.local && echo "  TLS 已设为 disabled"
regctl registry login harbor.wuxing.local -u admin -p "$CREDS" 2>&1 | tail -1
echo ""

echo "===== 2. 复制前状态 ====="
show "$H/$REPO:$TAG" "复制前 $REPO:$TAG"
echo ""

echo "===== 3. 分别推两个单架构到临时 tag ====="
echo ">>> amd64"
skopeo copy --override-arch amd64 --override-os linux \
  --dest-tls-verify=false --dest-creds "$CREDS" \
  "docker://$SRC" "docker://$H/$REPO:tmp-amd64" 2>&1 | tail -2
echo ">>> arm64"
skopeo copy --override-arch arm64 --override-os linux \
  --dest-tls-verify=false --dest-creds "$CREDS" \
  "docker://$SRC" "docker://$H/$REPO:tmp-arm64" 2>&1 | tail -2
echo ""
show "$H/$REPO:tmp-amd64" "临时 tag amd64"
show "$H/$REPO:tmp-arm64" "临时 tag arm64"
echo ""

echo "===== 4. regctl 组装 index 到正式 tag ====="
regctl image index create "$H/$REPO:$TAG" \
  --ref "$H/$REPO:tmp-amd64" \
  --ref "$H/$REPO:tmp-arm64" 2>&1 | tail -3
echo ""
show "$H/$REPO:$TAG" "组装后 $REPO:$TAG"
echo ""

echo "===== 5. 清理：删除临时 tag 和测试仓库 ====="
for t in tmp-amd64 tmp-arm64; do
  d=$(curl -sk -u "$CREDS" -o /dev/null -D - -H 'Accept: application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json' "https://$H/v2/$REPO/manifests/$t" 2>/dev/null | grep -i '^docker-content-digest' | tr -d '\r' | awk '{print $2}')
  if [ -n "$d" ]; then
    code=$(curl -sk -u "$CREDS" -o /dev/null -w '%{http_code}' -X DELETE "https://$H/v2/$REPO/manifests/$d")
    echo "  删除 $t ($d) -> HTTP $code"
  fi
done
# 删掉实验用的 exp-b 仓库
eb=$(curl -sk -u "$CREDS" "https://$H/api/v2.0/projects/library/repositories/exp-b" 2>/dev/null | python3 -c 'import sys,json; print(json.load(sys.stdin).get("name",""))' 2>/dev/null)
if [ -n "$eb" ]; then
  echo "  删除实验仓库 library/exp-b -> $(curl -sk -u "$CREDS" -o /dev/null -w '%{http_code}' -X DELETE "https://$H/api/v2.0/projects/library/repositories/exp-b")"
fi
echo ""
echo "===== 6. 最终状态 ====="
show "$H/$REPO:$TAG" "$REPO:$TAG"
echo -n "  tag 列表: "; curl -sk -u "$CREDS" "https://$H/v2/$REPO/tags/list" 2>/dev/null; echo
