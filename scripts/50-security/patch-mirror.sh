#!/bin/bash
# 为 /data1/ssdxt/images/mirror.sh 补 tetragon 清单（幂等，自动备份）
set -euo pipefail
F=/data1/ssdxt/images/mirror.sh
TS=$(date +%Y%m%d-%H%M%S)
[ -f "$F.bak.tetragon.$TS" ] || cp "$F" "$F.bak.tetragon.$TS"
if grep -q LIST_TETRAGON "$F"; then echo "已包含 tetragon 清单，跳过"; exit 0; fi
python3 - "$F" <<'EOF'
import sys
p=sys.argv[1]
s=open(p).read()
lst='''
LIST_TETRAGON='
quay.io/cilium/tetragon:v1.7.1|tetragon/tetragon:v1.7.1
quay.io/cilium/tetragon-operator:v1.7.1|tetragon/tetragon-operator:v1.7.1
quay.io/cilium/hubble-export-stdout:v1.1.1|tetragon/hubble-export-stdout:v1.1.1
quay.io/cilium/tetragon-rthooks:v0.8|tetragon/tetragon-rthooks:v0.8
'
'''
anchor="LIST_OTEL='"
s=s.replace(anchor, lst+"\nLIST_OTEL='",1)
s=s.replace('keda) LIST="$LIST_KEDA";;','keda) LIST="$LIST_KEDA";; tetragon) LIST="$LIST_TETRAGON";;',1)
s=s.replace('$LIST_OTEL$LIST_KEDA";;','$LIST_OTEL$LIST_KEDA$LIST_TETRAGON";;',1)
s=s.replace('[longhorn|logging|metrics|nfs|argocd|monitoring|otel|keda|all]','[longhorn|logging|metrics|nfs|argocd|monitoring|otel|keda|tetragon|all]')
# 项目创建循环里加 tetragon
s=s.replace('for p in longhorn logging metrics-server nfs-provisioner monitoring keda; do','for p in longhorn logging metrics-server nfs-provisioner monitoring keda tetragon; do')
open(p,'w').write(s)
print("patched")
EOF
bash -n "$F" && echo "语法 OK"
grep -n 'LIST_TETRAGON\|tetragon)' "$F" | head
