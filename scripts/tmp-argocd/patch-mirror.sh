#!/bin/bash
set -e
M=/data1/ssdxt/images/mirror.sh
cp "$M" "$M.bak.$(date +%m%d-%H%M%S)"

python3 - "$M" <<'EOF'
import sys
p = sys.argv[1]
s = open(p).read()
assert 'LIST_ARGOCD' not in s, 'already patched'
block = """LIST_ARGOCD='
quay.io/argoproj/argocd:v3.5.3|argocd/argocd:v3.5.3
public.ecr.aws/docker/library/redis:8.2.3-alpine|argocd/redis:8.2.3-alpine
ghcr.io/dexidp/dex:v2.45.1|argocd/dex:v2.45.1
'
"""
s = s.replace("case \"$TARGET\" in", block + "case \"$TARGET\" in", 1)
s = s.replace(
  "  metrics) LIST=\"$LIST_METRICS\";; nfs) LIST=\"$LIST_NFS\";;",
  "  metrics) LIST=\"$LIST_METRICS\";; nfs) LIST=\"$LIST_NFS\";; argocd) LIST=\"$LIST_ARGOCD\";;")
s = s.replace(
  "all) LIST=\"$LIST_LONGHORN$LIST_LOGGING$LIST_METRICS$LIST_NFS\";;",
  "all) LIST=\"$LIST_LONGHORN$LIST_LOGGING$LIST_METRICS$LIST_NFS$LIST_ARGOCD\";;")
open(p, 'w').write(s)
print("patched")
EOF
grep -n 'argocd' "$M"
