#!/bin/bash
export NO_PROXY='harbor.wuxing.local,10.100.10.29,localhost,127.0.0.1'
export no_proxy="$NO_PROXY"
H=harbor.wuxing.local
CREDS="admin:<HARBOR_PASSWORD>"
SRC=docker://docker.io/library/nginx:latest
R=$H/library/exp-c

show() {
  echo "--- $2"
  skopeo inspect --raw --tls-verify=false --creds "$CREDS" "docker://$1" 2>/dev/null | python3 -c '
import sys, json
try: d=json.load(sys.stdin)
except Exception: print("    (读取失败/不存在)"); raise SystemExit
if "manifests" not in d: print("    mediaType:", d.get("mediaType"), "-> 单架构")
else:
    p=[]
    for m in d["manifests"]:
        pl=m.get("platform") or {}
        a=pl.get("architecture")
        if a and a!="unknown": p.append(pl.get("os","?")+"/"+a)
    print("    mediaType:", d.get("mediaType"), "-> 架构数:", len(p), sorted(set(p)))
'
}

echo "===== 1. regctl 顶层 index 命令是否存在 ====="
regctl index --help 2>&1 | sed -n '1,25p'
echo ""
echo "===== 2. 推两个单架构到临时 tag ====="
skopeo copy --override-arch amd64 --override-os linux --dest-tls-verify=false --dest-creds "$CREDS" \
  "$SRC" "docker://$R:amd64" 2>&1 | tail -1
skopeo copy --override-arch arm64 --override-os linux --dest-tls-verify=false --dest-creds "$CREDS" \
  "$SRC" "docker://$R:arm64" 2>&1 | tail -1
show "$R:amd64" "临时 amd64"
show "$R:arm64" "临时 arm64"
echo ""

echo "===== 3. 方法一：regctl index create ====="
regctl registry set --tls disabled $H >/dev/null 2>&1
regctl registry login $H -u admin -p "$CREDS" >/dev/null 2>&1
regctl index create "$R:latest" --ref "$R:amd64" --ref "$R:arm64" 2>&1 | tail -3
show "$R:latest" "方法一结果"
echo ""

echo "===== 4. 若方法一失败，试方法二：buildx imagetools create ====="
if ! skopeo inspect --raw --tls-verify=false --creds "$CREDS" "docker://$R:latest" >/dev/null 2>&1; then
  echo "  方法一未产出，试 buildx..."
  docker buildx imagetools create -t "$R:latest" "$R:amd64" "$R:arm64" 2>&1 | tail -5
  show "$R:latest" "方法二结果"
else
  echo "  方法一已成功，跳过"
fi
echo ""

echo "===== 5. 当前 exp-c 的所有 tag ====="
curl -sk -u "$CREDS" "https://$H/v2/library/exp-c/tags/list" 2>/dev/null; echo
