#!/bin/bash
# 验证：精确只同步 linux/amd64 + linux/arm64 两个架构
# 效果：同一个 tag，一个 index 里恰好两个架构（不冗余、不改 tag）

export NO_PROXY='harbor.wuxing.local,10.100.10.29,localhost,127.0.0.1'
export no_proxy="$NO_PROXY"

H=harbor.wuxing.local
CREDS="admin:<HARBOR_PASSWORD>"

show() {
  local ref="$1" label="$2"
  echo "--- $label"
  skopeo inspect --raw --tls-verify=false --creds "$CREDS" "docker://$ref" 2>/dev/null | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    print("    读取失败"); raise SystemExit
if "manifests" not in d:
    print("    mediaType:", d.get("mediaType"))
    print("    -> 单架构 manifest")
else:
    print("    mediaType:", d.get("mediaType"))
    plats = []
    for m in d["manifests"]:
        p = m.get("platform") or {}
        a = p.get("architecture")
        if a and a != "unknown":
            v = ("/" + p["variant"]) if p.get("variant") else ""
            plats.append(p.get("os","?") + "/" + a + v)
    print("    -> 架构数:", len(plats))
    for x in sorted(set(plats)):
        print("       ", x)
'
}

echo "############################################################"
echo "# 测试 1：nginx —— 从 7 架构裁剪为恰好 amd64+arm64"
echo "############################################################"
show "$H/library/nginx:latest" "复制前"
echo ""
echo ">>> 执行命令："
echo "skopeo copy --multi-arch linux/amd64,linux/arm64 \\"
echo "  --dest-tls-verify=false --dest-creds admin:*** \\"
echo "  docker://docker.io/library/nginx:latest \\"
echo "  docker://$H/library/nginx:latest"
echo ""
time skopeo copy --multi-arch linux/amd64,linux/arm64 \
  --dest-tls-verify=false --dest-creds "$CREDS" \
  docker://docker.io/library/nginx:latest \
  docker://$H/library/nginx:latest 2>&1 | tail -4
echo ""
show "$H/library/nginx:latest" "复制后"

echo ""
echo "############################################################"
echo "# 测试 2：prometheus —— 从单架构 amd64 补齐为 amd64+arm64"
echo "############################################################"
show "$H/monitoring/prometheus:v2.54.1" "复制前"
echo ""
time skopeo copy --multi-arch linux/amd64,linux/arm64 \
  --dest-tls-verify=false --dest-creds "$CREDS" \
  docker://quay.io/prometheus/prometheus:v2.54.1 \
  docker://$H/monitoring/prometheus:v2.54.1 2>&1 | tail -4
echo ""
show "$H/monitoring/prometheus:v2.54.1" "复制后"

echo ""
echo "############################################################"
echo "# 确认 tag 没有变化（无冗余 tag）"
echo "############################################################"
for r in library/nginx monitoring/prometheus; do
  echo -n "  $r -> "
  curl -sk -u "$CREDS" "https://$H/v2/$r/tags/list" 2>/dev/null
  echo ""
done
