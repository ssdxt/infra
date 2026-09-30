#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== pods/log long-running gauge, per apiserver instance (via Prometheus) ==="
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/query?query=apiserver_longrunning_requests%7Bresource%3D%22pods%22%2Csubresource%3D%22log%22%7D' 2>&1 | python3 -c "
import sys,json
d=json.load(sys.stdin)
for r in d['data']['result']:
    print('  ', r['metric'].get('instance'), '->', r['value'][1])
if not d['data']['result']: print('   none')
" 2>&1

echo ""
echo "=== is anything STILL opening pods/log streams? rate over 5m ==="
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/query?query=sum(rate(apiserver_request_total%7Bresource%3D%22pods%22%2Csubresource%3D%22log%22%2Cverb%3D%22CONNECT%22%7D%5B5m%5D))' 2>&1 | python3 -c "
import sys,json
d=json.load(sys.stdin)
r=d['data']['result']
print('   new pods/log CONNECT per second (5m avg):', r[0]['value'][1] if r else 'none')
" 2>&1

echo ""
echo "=== total inflight (all 3 apiservers) ==="
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/query?query=sum(apiserver_current_inflight_requests)' 2>&1 | head -c 300
echo ""
echo "=== alloy restarts since rollout ==="
kubectl -n logging get pods -l app.kubernetes.io/name=alloy --no-headers | awk '{s+=$5} END {print "   alloy total restarts:", s}'
kubectl -n logging get ds alloy
echo "=== CSI restart totals ==="
kubectl -n longhorn-system get pods -l 'app in (csi-provisioner,csi-attacher,csi-resizer,csi-snapshotter)' --no-headers | awk '{s+=$5} END {print "   ", s}'
