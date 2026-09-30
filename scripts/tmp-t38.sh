#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
NOW=$(date +%s)
START=$((NOW-180))

echo "=== [1] CRI check: only lines written in the LAST 3 MIN (post-fix) ==="
kubectl -n logging exec loki-0 -c loki -- wget -qO- "http://localhost:3100/loki/api/v1/query_range?query=%7Bnamespace%3D%22longhorn-system%22%7D&start=${START}000000000&limit=6" 2>&1 | python3 -c "
import sys,json
d=json.load(sys.stdin)
res=d['data']['result']
if not res: print('  NO RESULTS in last 3 min'); sys.exit()
n=0
for s in res:
    for v in s['values']:
        line=v[1]
        bad='PREFIX-PRESENT' if (' stdout F ' in line or ' stderr F ' in line) else 'CLEAN'
        print(f'   [{bad}] stream={s[\"stream\"].get(\"stream\")} pod={s[\"stream\"].get(\"pod\")}')
        print(f'        {line[:130]!r}')
        n+=1
        if n>=4: sys.exit()
" 2>&1

echo ""
echo "=== [2] decay test: pods/log gauge + new-CONNECT rate, 6 samples / 30s ==="
for i in 1 2 3 4 5 6; do
  G=$(kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/query?query=sum(apiserver_longrunning_requests%7Bresource%3D%22pods%22%2Csubresource%3D%22log%22%7D)' 2>/dev/null | python3 -c "import sys,json; r=json.load(sys.stdin)['data']['result']; print(r[0]['value'][1] if r else '0')" 2>/dev/null)
  R=$(kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/query?query=sum(rate(apiserver_request_total%7Bresource%3D%22pods%22%2Csubresource%3D%22log%22%2Cverb%3D%22CONNECT%22%7D%5B1m%5D))' 2>/dev/null | python3 -c "import sys,json; r=json.load(sys.stdin)['data']['result']; print(r[0]['value'][1] if r else '0')" 2>/dev/null)
  echo "  t=$((i*30))s  pods/log gauge=${G:-?}  new-CONNECT/s=${R:-?}"
  sleep 30
done

echo ""
echo "=== [3] alloy restarts (should be 0 new since rollout) ==="
kubectl -n logging get pods -l app.kubernetes.io/name=alloy --no-headers | awk '{s+=$5} END {print "   total:", s}'
kubectl -n logging get pods -l app.kubernetes.io/name=alloy --no-headers | awk '{print $1, $2, $3, $5}' | head -12

echo ""
echo "=== [4] CSI restarts now vs earlier (54 at 15:25) ==="
kubectl -n longhorn-system get pods -l 'app in (csi-provisioner,csi-attacher,csi-resizer,csi-snapshotter)' --no-headers | awk '{s+=$5} END {print "   total:", s}'
echo "   timestamp: $(date +%H:%M:%S)"

echo ""
echo "=== [5] APF throttling evidence (429s) ==="
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/query?query=sum(increase(apiserver_request_terminations_total%7Bcode%3D%22429%22%7D%5B15m%5D))by(resource,verb)' 2>&1 | python3 -c "
import sys,json
d=json.load(sys.stdin)
for r in d['data']['result']:
    print('   429s last15m:', r['metric'].get('resource'), r['metric'].get('verb'), '->', r['value'][1])
" 2>&1
