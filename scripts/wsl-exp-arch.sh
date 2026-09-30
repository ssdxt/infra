#!/bin/bash
# 对照实验：找出"恰好 amd64+arm64"的可靠做法
export NO_PROXY='harbor.wuxing.local,10.100.10.29,localhost,127.0.0.1'
export no_proxy="$NO_PROXY"
H=harbor.wuxing.local
CREDS="admin:<HARBOR_PASSWORD>"
SRC=docker.io/library/nginx:latest

show() {
  echo "--- $2"
  skopeo inspect --raw --tls-verify=false --creds "$CREDS" "docker://$1" 2>/dev/null | python3 -c '
import sys, json
try: d = json.load(sys.stdin)
except Exception: print("    (读取失败/不存在)"); raise SystemExit
if "manifests" not in d:
    print("    mediaType:", d.get("mediaType"), "-> 单架构")
else:
    print("    mediaType:", d.get("mediaType"))
    p = []
    for m in d["manifests"]:
        pl = m.get("platform") or {}
        a = pl.get("architecture")
        if a and a != "unknown": p.append(pl.get("os","?")+"/"+a)
    print("    -> 架构数:", len(p), sorted(set(p)))
'
}

echo "===== 环境能力检查 ====="
echo -n "  docker buildx: "; docker buildx version 2>/dev/null | head -1 || echo "不可用"
echo -n "  regctl:        "; regctl version 2>/dev/null | grep VCSTag | head -1
echo -n "  regctl image index 子命令: "; regctl image index --help 2>&1 | grep -E '^\s+(add|create|delete|put)' | tr -s ' ' | tr '\n' ' '; echo
echo ""

echo "===== 实验 A：全新仓库 + --multi-arch 平台列表 ====="
echo "  目标: $H/library/exp-a:latest （全新，无历史 blob）"
skopeo copy --multi-arch linux/amd64,linux/arm64 \
  --dest-tls-verify=false --dest-creds "$CREDS" \
  "docker://$SRC" "docker://$H/library/exp-a:latest" 2>&1 | tail -5
echo "  退出码: $?"
show "$H/library/exp-a:latest" "实验A 结果"
echo ""

echo "===== 实验 B：全新仓库 + --multi-arch all ====="
echo "  目标: $H/library/exp-b:latest （全新）"
skopeo copy --multi-arch all \
  --dest-tls-verify=false --dest-creds "$CREDS" \
  "docker://$SRC" "docker://$H/library/exp-b:latest" 2>&1 | tail -3
echo "  退出码: $?"
show "$H/library/exp-b:latest" "实验B 结果"
