#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf

echo "=== [1] wait for real rollout (UP-TO-DATE must equal DESIRED) ==="
kubectl -n logging rollout status ds/alloy --timeout=420s 2>&1 | tail -3
kubectl -n logging get ds alloy

echo ""
echo "=== [2] pick a NEW pod (has varlog mount) and inspect ==="
for p in $(kubectl -n logging get pods -l app.kubernetes.io/name=alloy --no-headers | awk '{print $1}'); do
  if kubectl -n logging get pod $p -o jsonpath='{.spec.containers[0].volumeMounts[*].name}' 2>/dev/null | grep -q varlog; then
    NEWPOD=$p; break
  fi
done
echo "  new pod = $NEWPOD"
kubectl -n logging exec $NEWPOD -c alloy -- sh -c 'echo "  NODE_NAME=$NODE_NAME"; echo "  /var/log/pods dirs: $(ls /var/log/pods 2>/dev/null | wc -l)"; echo "  matching .log files: $(ls /var/log/pods/*/*/*.log 2>/dev/null | wc -l)"; echo "  sample: $(ls /var/log/pods/*/*/*.log 2>/dev/null | head -1)"' 2>&1

echo ""
echo "=== [3] alloy logs: config loaded / errors? ==="
kubectl -n logging logs $NEWPOD -c alloy --tail=25 2>&1 | grep -iE 'error|level=error|finished complete graph|scheduling loaded|local.file_match|loki.source.file' | tail -12

echo ""
echo "=== [4] wait 100s for file tailing to push logs ==="
sleep 100
echo "--- Loki labels ---"
kubectl -n logging exec loki-0 -c loki -- wget -qO- 'http://localhost:3100/loki/api/v1/labels' 2>&1 | head -c 400
echo ""
echo "--- namespace label values ---"
kubectl -n logging exec loki-0 -c loki -- wget -qO- 'http://localhost:3100/loki/api/v1/label/namespace/values' 2>&1 | head -c 400
echo ""
echo "=== [5] RAW log line (check for CRI prefix 'stdout F') ==="
kubectl -n logging exec loki-0 -c loki -- wget -qO- 'http://localhost:3100/loki/api/v1/query_range?query=%7Bnamespace%3D%22longhorn-system%22%7D&limit=2' 2>&1 | python3 -c "
import sys,json
d=json.load(sys.stdin)
res=d['data']['result']
if not res: print('  NO RESULTS')
for s in res[:2]:
    print('  labels:', json.dumps(s['stream'],ensure_ascii=False))
    for v in s['values'][:2]:
        print('   ts=',v[0],' line=',repr(v[1][:170]))
" 2>&1

echo ""
echo "=== [6] AFTER: apiserver pods/log long-running streams ==="
for i in 1 2 3; do
  v=$(kubectl get --raw='/metrics' 2>/dev/null | grep '^apiserver_longrunning_requests{' | grep 'subresource="log"' | awk '{print $2}')
  echo "  sample$i pods/log streams = ${v:-0}"
  sleep 6
done
echo "  inflight after:"; kubectl get --raw='/metrics' 2>/dev/null | grep '^apiserver_current_inflight_requests'
echo "  CSI restart totals now:"
kubectl -n longhorn-system get pods -l 'app in (csi-provisioner,csi-attacher,csi-resizer,csi-snapshotter)' --no-headers | awk '{s+=$5} END {print "   ", s}'
echo "  timestamp: $(date +%H:%M:%S)"
