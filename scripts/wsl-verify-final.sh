#!/bin/bash
export NO_PROXY='harbor.wuxing.local,10.100.10.29,localhost,127.0.0.1'
export no_proxy="$NO_PROXY"
H=harbor.wuxing.local
USER=admin
PASS='<HARBOR_PASSWORD>'
T=$H/library/exp-d

echo "===== 1. 验证 index 里的两个架构是否真的可解析（blob 是否真在）====="
for a in amd64 arm64; do
  echo -n "  linux/$a -> "
  regctl image inspect --platform linux/$a "$T:latest" 2>/dev/null | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
    print("OK  架构=%s 大小=%sMB" % (d.get("architecture"), round(int(d.get("size",0))/1048576,1)))
except Exception:
    print("✗ 解析失败（blob 可能缺失）")
'
done

echo ""
echo "===== 2. 用 skopeo 实测能否按架构拉取（真正的端到端验证）====="
for a in amd64 arm64; do
  echo -n "  skopeo 拉取 linux/$a 的配置: "
  skopeo inspect --override-arch $a --override-os linux \
    --tls-verify=false --creds "$USER:$PASS" "docker://$T:latest" 2>/dev/null | \
    python3 -c 'import sys,json; d=json.load(sys.stdin); print("✓ OK  Created=%s" % d.get("Created","")[:19])' 2>/dev/null || echo "✗ 失败"
done

echo ""
echo "===== 3. 清理测试仓库 exp-d ====="
echo "  HTTP $(curl -sk -u "$USER:$PASS" -o /dev/null -w '%{http_code}' -X DELETE "https://$H/api/v2.0/projects/library/repositories/exp-d")"

echo ""
echo "===== 4. Harbor 现状复核（重点仓库）====="
for r in library/nginx monitoring/prometheus coredns/coredns; do
  echo -n "  $r: "
  skopeo inspect --raw --tls-verify=false --creds "$USER:$PASS" "docker://$H/$r:latest" 2>/dev/null | python3 -c '
import sys,json
try: d=json.load(sys.stdin)
except Exception: print("(读取失败)"); raise SystemExit
if "manifests" not in d: print("单架构")
else:
    p=set()
    for m in d["manifests"]:
        pl=m.get("platform") or {}
        a=pl.get("architecture")
        if a and a!="unknown": p.add(pl.get("os","?")+"/"+a)
    print("多架构:", sorted(p))
' 2>/dev/null || echo "(tag 不存在)"
done
echo -n "  monitoring/prometheus:v2.54.1: "
skopeo inspect --raw --tls-verify=false --creds "$USER:$PASS" "docker://$H/monitoring/prometheus:v2.54.1" 2>/dev/null | python3 -c '
import sys,json
d=json.load(sys.stdin)
p=set()
for m in d.get("manifests",[]):
    pl=m.get("platform") or {}
    a=pl.get("architecture")
    if a and a!="unknown": p.add(pl.get("os","?")+"/"+a)
print(sorted(p) if p else "单架构")
'
