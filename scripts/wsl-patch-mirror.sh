#!/bin/bash
# 在 WSL 里：备份 mirror.sh → 补上 k8s-sidecar → 重新搬 logging
set -u
cp ~/mirror.sh ~/mirror.sh.bak.$(date +%m%d-%H%M%S)
python3 - <<'PY'
import io,os
p=os.path.expanduser('~/mirror.sh')
s=open(p).read()
new='kiwigrid/k8s-sidecar:1.28.0|logging/k8s-sidecar:1.28.0\n'
anchor='grafana/alloy:v1.7.0|logging/alloy:v1.7.0\n'
if 'k8s-sidecar' in s:
    print('already present, skip')
elif anchor in s:
    s=s.replace(anchor, anchor+new, 1)
    open(p,'w').write(s)
    print('inserted after alloy line')
else:
    raise SystemExit('ANCHOR NOT FOUND - aborting')
PY
echo "=== LIST_LOGGING now ==="
sed -n '/^LIST_LOGGING=/,/^'"'"'/p' ~/mirror.sh
echo ""
echo "=== run mirror logging ==="
bash ~/mirror.sh logging
