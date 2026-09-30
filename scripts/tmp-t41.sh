#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== [1] alloy pods: status / restarts / last exit reason ==="
kubectl -n logging get pods -l app.kubernetes.io/name=alloy -o custom-columns='NAME:.metadata.name,READY:.status.containerStatuses[0].ready,STATUS:.status.phase,RESTARTS:.status.containerStatuses[0].restartCount,LASTREASON:.status.containerStatuses[0].lastState.terminated.reason,EXIT:.status.containerStatuses[0].lastState.terminated.exitCode' 2>&1 | head -14

echo ""
echo "=== [2] describe one: OOMKilled? ==="
P=$(kubectl -n logging get pods -l app.kubernetes.io/name=alloy --no-headers | awk '{print $1}' | head -1)
kubectl -n logging describe pod $P 2>&1 | grep -A6 -E 'Last State|Limits|Requests|Reason' | head -25

echo ""
echo "=== [3] alloy logs before crash (tail of one) ==="
kubectl -n logging logs $P -c alloy --tail=25 2>&1 | tail -25

echo ""
echo "=== [4] previous (crashed) container logs ==="
kubectl -n logging logs $P -c alloy --previous --tail=25 2>&1 | tail -25

echo ""
echo "=== [5] memory usage of alloy pods ==="
kubectl top pods -n logging 2>&1 | head -14

echo ""
echo "=== [6] namespace=None streams: which filenames? ==="
kubectl -n logging exec loki-0 -c loki -- wget -qO- 'http://localhost:3100/loki/api/v1/query_range?query=%7Bjob%3D%22pods%22%2Cnamespace%3D%22%22%7D&limit=3' 2>&1 | head -c 500
echo ""
kubectl -n logging exec loki-0 -c loki -- wget -qO- 'http://localhost:3100/loki/api/v1/series?match%5B%5D=%7Bjob%3D%22pods%22%7D&limit=40' 2>&1 | python3 -c "
import sys,json
try: d=json.load(sys.stdin)
except: print('  (series query failed)'); sys.exit()
seen=set()
for s in d.get('data',[]):
    fn=s.get('filename','')
    if not s.get('namespace'):
        print('  NO-NS file:', fn[:110])
        seen.add(fn)
    if len(seen)>5: break
print('  total series:', len(d.get('data',[])))
" 2>&1
