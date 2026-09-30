#!/bin/bash
export NO_PROXY='harbor.wuxing.local,10.100.10.29,localhost,127.0.0.1'
export no_proxy="$NO_PROXY"
H=harbor.wuxing.local
USER=admin
PASS='<HARBOR_PASSWORD>'
CA="$(cat /mnt/c/Users/CC/Desktop/dsh/harbor-real-ca.crt)"
REPO=monitoring/prometheus
TAG=v2.54.1
SRC=docker://quay.io/prometheus/prometheus:v2.54.1

show() {
  echo "--- $2"
  skopeo inspect --raw --tls-verify=false --creds "$USER:$PASS" "docker://$1" 2>/dev/null | python3 -c '
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

echo "===== 0. 现状（确认 tag 丢失）====="
echo -n "  tags: "; curl -sk -u "$USER:$PASS" "https://$H/v2/$REPO/tags/list" 2>/dev/null; echo
echo ""

echo "===== 1. regctl 正确登录 ====="
regctl registry set $H --cacert "$CA" >/dev/null 2>&1
regctl registry login $H -u "$USER" -p "$PASS" 2>&1 | tail -1
echo -n "  验证: "
regctl repo ls $H 2>/dev/null | wc -l | xargs -I{} echo "{} 个仓库可见"
echo ""

echo "===== 2. 重新推两个架构到临时 tag ====="
for a in amd64 arm64; do
  echo ">>> $a"
  skopeo copy --override-arch $a --override-os linux \
    --dest-tls-verify=false --dest-creds "$USER:$PASS" \
    "$SRC" "docker://$H/$REPO:tmp-$a" 2>&1 | tail -1
done
echo ""

echo "===== 3. 组装恰好两架构的 index → 正式 tag ====="
regctl index create "$H/$REPO:$TAG" \
  --ref "$H/$REPO:tmp-amd64" \
  --ref "$H/$REPO:tmp-arm64" 2>&1 | tail -3
echo ""
show "$H/$REPO:$TAG" "组装后 $REPO:$TAG"
echo ""

echo "===== 4. 只删除临时 TAG（用 Harbor 标签 API，绝不能按 digest 删 manifest）====="
for t in tmp-amd64 tmp-arm64; do
  code=$(curl -sk -u "$USER:$PASS" -o /dev/null -w '%{http_code}' -X DELETE \
    "https://$H/api/v2.0/projects/monitoring/repositories/prometheus/artifacts/tmp-$t/tags/tmp-$t")
  echo "  删 tag tmp-$t -> HTTP $code"
done
# 上面按 tag 名定位 artifact 可能不对，改用逐个 tag 精确删除
for t in tmp-amd64 tmp-arm64; do
  # 找到该 tag 对应的 artifact digest
  dig=$(curl -sk -u "$USER:$PASS" "https://$H/api/v2.0/projects/monitoring/repositories/prometheus/artifacts?with_tag=true&page_size=50" 2>/dev/null | python3 -c "
import sys,json
try: d=json.load(sys.stdin)
except Exception: raise SystemExit
for a in d:
    for tg in (a.get('tags') or []):
        if tg['name']=='$t': print(a['digest'])
" 2>/dev/null)
  if [ -n "$dig" ]; then
    code=$(curl -sk -u "$USER:$PASS" -o /dev/null -w '%{http_code}' -X DELETE \
      "https://$H/api/v2.0/projects/monitoring/repositories/prometheus/artifacts/$dig/tags/$t")
    echo "  精确删除 tag $t (artifact $dig) -> HTTP $code"
  fi
done
echo ""
echo "===== 5. 最终验证 ====="
echo -n "  tags: "; curl -sk -u "$USER:$PASS" "https://$H/v2/$REPO/tags/list" 2>/dev/null; echo
show "$H/$REPO:$TAG" "最终 $REPO:$TAG"
