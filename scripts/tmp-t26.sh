#!/bin/bash
# Add clarifying comment about the mandatory `targets` param, then final stability check
set -u
export KUBECONFIG=/etc/kubernetes/admin.conf
F=/data1/ssdxt/logging/02-alloy.sh
TS=$(date +%m%d-%H%M%S)

echo "=== [1] annotate 02-alloy.sh (backup first) ==="
cp -a $F $F.bak.$TS && echo "  backup: $F.bak.$TS"
python3 - <<'PY'
p = '/data1/ssdxt/logging/02-alloy.sh'
s = open(p, encoding='utf-8').read()
old = '# Alloy 配置：采集容器日志 → 推 Loki'
new = ('# Alloy 配置：采集容器日志 → 推 Loki\n'
       '# 注意: discovery.relabel 必须显式声明 targets，否则 Alloy 启动即报\n'
       '#       "Error: could not perform the initial load successfully" 并 CrashLoop')
if 'must explicitly declare' in s or '必须显式声明 targets' in s:
    print('  already annotated, skip')
elif old in s:
    open(p, 'w', encoding='utf-8').write(s.replace(old, new, 1))
    print('  comment added')
else:
    print('  anchor not found, skip')
PY
sed -n '1,20p' $F

echo ""
echo "=== [2] stability watch: CSI + alloy pods for 180s ==="
for i in 1 2 3 4 5 6; do
  bad=$(kubectl -n longhorn-system get pods --no-headers | grep -vcE 'Running|Completed')
  csi=$(kubectl -n longhorn-system get pods -l 'app in (csi-provisioner,csi-attacher,csi-resizer,csi-snapshotter)' --no-headers 2>/dev/null | awk '{print $3}' | sort | uniq -c | tr '\n' ' ')
  echo "  t=$((i*30))s  longhorn-not-running=$bad  csi-statuses: $csi"
  sleep 30
done

echo ""
echo "=== [3] FINAL STATE ==="
echo "--- longhorn pods ---"
kubectl -n longhorn-system get pods --no-headers | awk '{print $2, $3}' | sort | uniq -c
kubectl -n longhorn-system get pods --no-headers | grep -vE 'Running|Completed' || echo "  no pod in bad state"
echo "--- restarts in last 8 min (all longhorn pods) ---"
kubectl -n longhorn-system get pods -o json | python3 -c "
import sys,json,datetime
d=json.load(sys.stdin); now=datetime.datetime.now(datetime.timezone.utc); n=0
for p in d['items']:
    for cs in (p['status'].get('containerStatuses') or []):
        lc=cs.get('lastState',{}).get('terminated')
        if lc and lc.get('finishedAt'):
            dt=datetime.datetime.fromisoformat(lc['finishedAt'].replace('Z','+00:00'))
            if (now-dt).total_seconds()<480:
                n+=1; print('   ',(now-dt).total_seconds()/60, 'min ago', p['metadata']['name'], cs['name'], 'exit', lc.get('exitCode'))
print('   crashes in last 8 min:', n)
"
echo ""
echo "--- logging ---"
kubectl -n logging get ds alloy
kubectl -n logging get pods --no-headers | awk '{print $2, $3}' | sort | uniq -c
echo "--- SC ---"
kubectl get sc
echo "--- top nodes (first 3) ---"
kubectl top nodes | head -4
echo "--- LogQL final sample ---"
kubectl -n logging exec loki-0 -c loki -- wget -qO- 'http://localhost:3100/loki/api/v1/query?query=sum(count_over_time(%7Bnamespace%3D~%22.%2B%22%7D%5B5m%5D))by(namespace)' 2>&1 | head -c 400
