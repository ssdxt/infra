#!/bin/bash
PKG=/root/anaconda3/envs/recovery/lib/python3.8/site-packages
BK=/deploy/cc/logs/pkg-backup-20260914-093505/mixed-cleanup
PLAN=$BK/cleanup-plan-v2.json

echo "########## 1. 待删文件总大小估算 ##########"
python3 - <<'EOF'
import json, os, collections
PKG="/root/anaconda3/envs/recovery/lib/python3.8/site-packages"
plan=json.load(open("/deploy/cc/logs/pkg-backup-20260914-093505/mixed-cleanup/cleanup-plan-v2.json"))
tot=0; cnt=0; top=[]
for p in plan:
    s=0
    for f in p["drop_files"]:
        fp=os.path.join(PKG,f)
        if os.path.exists(fp):
            try: s+=os.path.getsize(fp)
            except Exception: pass
    tot+=s; cnt+=len(p["drop_files"])
    if s>10*1024*1024: top.append((s,p["name"]))
print(f"  文件数: {cnt}")
print(f"  总大小: {tot/1024/1024:.1f} MB")
print("  超过 10MB 的包:")
for s,n in sorted(top, reverse=True)[:10]:
    print(f"    {n:26} {s/1024/1024:8.1f} MB")
EOF

echo
echo "########## 2. /deploy 可用空间 ##########"
df -h /deploy | tail -1

echo
echo "########## 3. 执行清理（移动到备份目录）##########"
cd /tmp || exit 1
python3 /tmp/cleanup2.py --apply 2>&1 | tail -8

echo
echo "########## 4. 清理后校验：每个包只剩一个 dist-info ##########"
python3 - <<'EOF'
import os, re, collections
PKG="/root/anaconda3/envs/recovery/lib/python3.8/site-packages"
pat=re.compile(r"^(?P<name>.+?)-(?P<ver>\d[^-]*)\.dist-info$")
g=collections.defaultdict(list)
for d in os.listdir(PKG):
    m=pat.match(d)
    if m: g[m.group("name").lower().replace("_","-")].append(m.group("ver"))
dups={k:v for k,v in g.items() if len(v)>1}
print(f"  仍有多版本 dist-info 的包: {len(dups)}")
for k,v in list(dups.items())[:10]: print(f"    {k}: {v}")
EOF

echo
echo "########## 5. 关键包版本复核 ##########"
/root/anaconda3/envs/recovery/bin/python - <<'EOF'
import importlib.metadata as m
for p in ["fastapi","charset-normalizer","tokenizers","transformers","torch","starlette","pydantic"]:
    try: print(f"  {p:22} {m.version(p)}")
    except Exception as e: print(f"  {p:22} <错误: {e}>")
EOF
