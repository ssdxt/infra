#!/bin/bash
# Add stage.cri {} so the CRI prefix ('<ts> stdout F ') is parsed off the log line
set -u
export KUBECONFIG=/etc/kubernetes/admin.conf
F=/data1/ssdxt/logging/02-alloy.sh
TS=$(date +%m%d-%H%M%S)

echo "=== [1] backup + patch script ==="
cp -a $F $F.bak.$TS && echo "  backup: $F.bak.$TS"
python3 - <<'PY'
p='/data1/ssdxt/logging/02-alloy.sh'
s=open(p,encoding='utf-8').read()
anchor='        // 从文件路径解析 namespace / pod / pod_uid / container\n'
add = ('        // containerd 写的是 CRI 格式: "<ts> stdout|stderr F <msg>"\n'
       '        // 必须先用 cri 阶段剥掉前缀，否则日志行会带上时间戳和 stdout F\n'
       '        stage.cri {}\n')
if 'stage.cri' in s:
    print('  already present, skip')
elif anchor in s:
    open(p,'w',encoding='utf-8').write(s.replace(anchor, add+anchor, 1))
    print('  inserted stage.cri')
else:
    print('  ANCHOR NOT FOUND')
PY
bash -n $F && echo "  bash syntax OK"
sed -n '/loki.process "pods"/,/forward_to = \[loki.write/p' $F

echo ""
echo "=== [2] helm upgrade ==="
bash $F 2>&1 | tail -8

echo ""
echo "=== [3] wait for rollout ==="
kubectl -n logging rollout status ds/alloy --timeout=420s 2>&1 | tail -2
kubectl -n logging get ds alloy

echo ""
echo "=== [4] wait 90s then check log line is CLEAN (no 'stdout F' prefix) ==="
sleep 90
kubectl -n logging exec loki-0 -c loki -- wget -qO- 'http://localhost:3100/loki/api/v1/query_range?query=%7Bnamespace%3D%22longhorn-system%22%7D&limit=2' 2>&1 | python3 -c "
import sys,json
d=json.load(sys.stdin)
res=d['data']['result']
if not res: print('  NO RESULTS'); sys.exit()
for s in res[:2]:
    print('  labels:', json.dumps(s['stream'],ensure_ascii=False))
    for v in s['values'][:2]:
        line=v[1]
        bad=' CRI-PREFIX-STILL-PRESENT' if (' stdout F ' in line or ' stderr F ' in line) else ' clean'
        print('   line=',repr(line[:150]),'->',bad)
" 2>&1
echo ""
echo "  labels list:"
kubectl -n logging exec loki-0 -c loki -- wget -qO- 'http://localhost:3100/loki/api/v1/labels' 2>&1 | head -c 300
