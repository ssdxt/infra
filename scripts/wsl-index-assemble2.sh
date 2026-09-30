#!/bin/bash
export NO_PROXY='harbor.wuxing.local,10.100.10.29,localhost,127.0.0.1'
export no_proxy="$NO_PROXY"
H=harbor.wuxing.local
CREDS="admin:<HARBOR_PASSWORD>"
R=$H/library/exp-c
HOSTSPEC="reg=$H,tls=disabled,user=admin,pass=<HARBOR_PASSWORD>"

echo "===== 1. regctl index create 的参数 ====="
regctl index create --help 2>&1 | sed -n '1,30p'
echo ""

echo "===== 2. 检查 regctl 已保存的 registry 配置 ====="
regctl registry get $H 2>&1 | head -6
echo ""

echo "===== 3. 用全局 --host 内联参数组装 index ====="
regctl --host "$HOSTSPEC" index create "$R:latest" \
  --ref "$R:amd64" --ref "$R:arm64" 2>&1 | tail -4
echo ""
echo "--- 结果:"
skopeo inspect --raw --tls-verify=false --creds "$CREDS" "docker://$R:latest" 2>/dev/null | python3 -c '
import sys,json
try: d=json.load(sys.stdin)
except Exception: print("    (不存在)"); raise SystemExit
if "manifests" not in d: print("    单架构:", d.get("mediaType"))
else:
    p=[]
    for m in d["manifests"]:
        pl=m.get("platform") or {}
        a=pl.get("architecture")
        if a and a!="unknown": p.append(pl.get("os","?")+"/"+a)
    print("    mediaType:", d.get("mediaType"))
    print("    架构数:", len(p), sorted(set(p)))
'
echo ""
echo "===== 4. exp-c 的 tag 列表 ====="
curl -sk -u "$CREDS" "https://$H/v2/library/exp-c/tags/list" 2>/dev/null; echo
echo ""
echo "===== 5. 尝试把 Harbor CA 装进 WSL 信任库（长期方案）====="
if sudo -n true 2>/dev/null; then
  echo "  sudo 免密可用"
  sudo cp /mnt/c/Users/CC/Desktop/dsh/harbor-ca.crt /usr/local/share/ca-certificates/harbor-wuxing.crt 2>/dev/null && \
  sudo update-ca-certificates 2>&1 | tail -2
  echo -n "  验证（不带 -k 访问 Harbor）: "
  curl -s -o /dev/null -w '%{http_code}\n' --max-time 10 https://harbor.wuxing.local/v2/ 2>&1
else
  echo "  sudo 需要密码，跳过 CA 安装（改用 --host tls=disabled 方案即可）"
fi
