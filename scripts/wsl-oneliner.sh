#!/bin/bash
export NO_PROXY='harbor.wuxing.local,10.100.10.29,localhost,127.0.0.1'
export no_proxy="$NO_PROXY"
H=harbor.wuxing.local
USER=admin
PASS='<HARBOR_PASSWORD>'
CA="$(cat /mnt/c/Users/CC/Desktop/dsh/harbor-real-ca.crt)"
T=$H/library/exp-d

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
    print("    -> 架构数:", len(p), sorted(set(p)))
'
}

regctl registry set $H --cacert "$CA" >/dev/null 2>&1
regctl registry login $H -u "$USER" -p "$PASS" >/dev/null 2>&1

echo "===== 一条命令测试：regctl index create --ref 远程源 --platform 过滤 ====="
echo "命令："
echo "regctl index create $T:latest \\"
echo "  --ref docker.io/library/nginx:latest \\"
echo "  --platform linux/amd64 --platform linux/arm64"
echo ""
regctl index create "$T:latest" \
  --ref docker.io/library/nginx:latest \
  --platform linux/amd64 --platform linux/arm64 2>&1 | tail -5
echo ""
show "$T:latest" "一条命令的结果"
echo ""
echo "===== 若失败，看是否需要子 manifest 预先存在 ====="
echo -n "  exp-d tags: "; curl -sk -u "$USER:$PASS" "https://$H/v2/library/exp-d/tags/list" 2>/dev/null; echo
