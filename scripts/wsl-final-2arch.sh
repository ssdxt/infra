#!/bin/bash
export NO_PROXY='harbor.wuxing.local,10.100.10.29,localhost,127.0.0.1'
export no_proxy="$NO_PROXY"
H=harbor.wuxing.local
CREDS="admin:<HARBOR_PASSWORD>"
CA="$(cat /mnt/c/Users/CC/Desktop/dsh/harbor-real-ca.crt)"
R=$H/monitoring/prometheus
SRC=docker://quay.io/prometheus/prometheus:v2.54.1

show() {
  echo "--- $2"
  skopeo inspect --raw --tls-verify=false --creds "$CREDS" "docker://$1" 2>/dev/null | python3 -c '
import sys,json
try: d=json.load(sys.stdin)
except Exception: print("    (不存在)"); raise SystemExit
if "manifests" not in d: print("    mediaType:", d.get("mediaType"), "-> 单架构")
else:
    p=[]
    for m in d["manifests"]:
        pl=m.get("platform") or {}
        a=pl.get("architecture")
        if a and a!="unknown": p.append(pl.get("os","?")+"/"+a)
    print("    mediaType:", d.get("mediaType"))
    print("    ✓ 架构数:", len(p), sorted(set(p)))
'
}

echo "===== 1. 配置 regctl 信任 Harbor CA ====="
regctl registry set $H --cacert "$CA" && echo "  --cacert 已设置"
regctl registry login $H -u admin -p "$CREDS" 2>&1 | tail -1
echo -n "  验证 regctl 访问 Harbor: "
if regctl repo ls $H 2>&1 | head -1 >/dev/null; then
  echo "✓ 成功（$(regctl repo ls $H 2>/dev/null | wc -l) 个仓库）"
else
  echo "✗ 失败"; regctl repo ls $H 2>&1 | tail -2
fi
echo ""

echo "===== 2. 当前 prometheus 状态 ====="
show "$R:v2.54.1" "修复前"
echo ""

echo "===== 3. 推两个单架构到临时 tag ====="
for a in amd64 arm64; do
  echo ">>> $a"
  skopeo copy --override-arch $a --override-os linux \
    --dest-tls-verify=false --dest-creds "$CREDS" \
    "$SRC" "docker://$R:tmp-$a" 2>&1 | tail -1
done
echo ""

echo "===== 4. regctl 组装成恰好两架构的 index ====="
regctl index create "$R:v2.54.1" \
  --ref "$R:tmp-amd64" \
  --ref "$R:tmp-arm64" 2>&1 | tail -3
echo ""
show "$R:v2.54.1" "修复后"
echo ""

echo "===== 5. 删除临时 tag ====="
for t in tmp-amd64 tmp-arm64; do
  d=$(curl -sk -u "$CREDS" -o /dev/null -D - -H 'Accept: application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json' "https://$H/v2/monitoring/prometheus/manifests/$t" 2>/dev/null | grep -i '^docker-content-digest' | tr -d '\r' | awk '{print $2}')
  [ -n "$d" ] && echo "  删 $t -> HTTP $(curl -sk -u "$CREDS" -o /dev/null -w '%{http_code}' -X DELETE "https://$H/v2/monitoring/prometheus/manifests/$d")"
done
echo -n "  最终 tag: "; curl -sk -u "$CREDS" "https://$H/v2/monitoring/prometheus/tags/list" 2>/dev/null; echo
echo ""

echo "===== 6. 清理空测试仓库 exp-c ====="
echo "  $(curl -sk -u "$CREDS" -o /dev/null -w '%{http_code}' -X DELETE "https://$H/api/v2.0/projects/library/repositories/exp-c")"
