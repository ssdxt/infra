#!/bin/bash
cd /home/cc/charts2
echo "########## Longhorn 全部镜像（从 values.yaml 提取）##########"
helm show values longhorn-1.7.2.tgz 2>/dev/null | python3 -c '
import sys, re
lines = sys.stdin.read().split("\n")
cur = {}
out = []
for ln in lines:
    s = ln.strip()
    if s.startswith("repository:"):
        cur["repo"] = s.split(":",1)[1].strip().strip(chr(34))
    elif s.startswith("tag:"):
        cur["tag"] = s.split(":",1)[1].strip().strip(chr(34))
        if "repo" in cur and "tag" in cur:
            out.append(cur["repo"] + ":" + cur["tag"]); cur = {}
    elif s.startswith("registry:") and "repo" in cur:
        pass
seen = []
for x in out:
    if x not in seen: seen.append(x)
for x in sorted(seen): print(" ", x)
print("  小计:", len(seen))
'
echo ""
echo "########## Loki 镜像 ##########"
helm show values loki-6.24.0.tgz 2>/dev/null | python3 -c '
import sys
lines = sys.stdin.read().split("\n")
cur={}; out=[]
for ln in lines:
    s=ln.strip()
    if s.startswith("repository:"):
        cur["repo"]=s.split(":",1)[1].strip().strip(chr(34))
    elif s.startswith("tag:"):
        cur["tag"]=s.split(":",1)[1].strip().strip(chr(34))
        if "repo" in cur and "tag" in cur: out.append(cur["repo"]+":"+cur["tag"]); cur={}
seen=[]
for x in out:
    if x not in seen: seen.append(x)
for x in sorted(seen): print(" ", x)
'
echo ""
echo "########## Alloy 镜像 ##########"
helm show values alloy-0.12.0.tgz 2>/dev/null | python3 -c '
import sys
lines=sys.stdin.read().split("\n")
cur={}; out=[]
for ln in lines:
    s=ln.strip()
    if s.startswith("repository:"):
        cur["repo"]=s.split(":",1)[1].strip().strip(chr(34))
    elif s.startswith("tag:"):
        cur["tag"]=s.split(":",1)[1].strip().strip(chr(34))
        if "repo" in cur and "tag" in cur: out.append(cur["repo"]+":"+cur["tag"]); cur={}
seen=[]
for x in out:
    if x not in seen: seen.append(x)
for x in sorted(seen): print(" ", x)
'
