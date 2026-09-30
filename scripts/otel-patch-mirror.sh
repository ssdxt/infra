#!/bin/bash
set -e
F=/data1/ssdxt/images/mirror.sh
python3 - "$F" <<'EOF'
import sys
p = sys.argv[1]
s = open(p).read()
s = s.replace("argocd/dex:v2.45.1\n'\n'\nLIST_OTEL='", "argocd/dex:v2.45.1\n'\nLIST_OTEL='")
open(p, 'w').write(s)
EOF
bash -n "$F" && echo 'syntax OK'
bash "$F" otel 2>&1 | tail -5
