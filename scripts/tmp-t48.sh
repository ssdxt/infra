#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=longhorn-system
q() { kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- "http://localhost:9090/api/v1/query?query=$1" 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin); r=d['data']['result']
print('   %-56s -> %s' % ('$2', r[0]['value'][1] if r else 'n/a'))
" 2>/dev/null; }

echo "############ A. secrets API traffic breakdown (/s) ############"
q 'sum(rate(apiserver_request_total%7Bresource%3D%22secrets%22%2Cverb%3D%22GET%22%7D%5B5m%5D))' 'secrets GET /s'
q 'sum(rate(apiserver_request_total%7Bresource%3D%22secrets%22%2Cverb%3D%22PUT%22%7D%5B5m%5D))' 'secrets PUT /s (all codes)'
q 'sum(rate(apiserver_request_total%7Bresource%3D%22secrets%22%2Cverb%3D%22PUT%22%2Ccode%3D%22409%22%7D%5B5m%5D))' 'secrets PUT 409 /s'
q 'sum(rate(apiserver_request_total%7Bresource%3D%22secrets%22%2Cverb%3D%22PUT%22%2Ccode%3D%22200%22%7D%5B5m%5D))' 'secrets PUT 200 (committed) /s'
q 'sum(rate(apiserver_request_total%5B5m%5D))' 'ALL apiserver requests /s'
q 'sum(rate(apiserver_request_total%7Bverb%3D~%22POST%7CPUT%7CPATCH%7CDELETE%22%7D%5B5m%5D))' 'ALL write requests /s'
q 'sum(rate(apiserver_request_total%7Bresource%3D%22secrets%22%2Cverb%3D%22PUT%22%7D%5B5m%5D)) / sum(rate(apiserver_request_total%7Bverb%3D~%22POST%7CPUT%7CPATCH%7CDELETE%22%7D%5B5m%5D)) * 100' 'secrets PUT as % of all writes'
q 'sum(apiserver_longrunning_requests%7Bresource%3D%22secrets%22%2Cverb%3D%22WATCH%22%7D)' 'secret WATCH streams (fan-out)'
q 'sum(rate(apiserver_request_total%7Bresource%3D%22secrets%22%2Cverb%3D%22PUT%22%2Ccode%3D%22200%22%7D%5B5m%5D)) * sum(apiserver_longrunning_requests%7Bresource%3D%22secrets%22%2Cverb%3D%22WATCH%22%7D)' 'watch events/s caused by committed writes'

echo ""
echo "############ B. webhook config + failurePolicy ############"
for w in longhorn-webhook-validator longhorn-webhook-mutator; do
  echo "  == $w =="
  kubectl get validatingwebhookconfiguration $w -o json 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)
for x in d.get('webhooks',[]):
    print('    name=%s failurePolicy=%s timeout=%s rules=%d' % (x['name'], x.get('failurePolicy'), x.get('timeoutSeconds'), len(x.get('rules',[]))))
" 2>/dev/null
  kubectl get mutatingwebhookconfiguration $w -o json 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)
for x in d.get('webhooks',[]):
    print('    name=%s failurePolicy=%s timeout=%s rules=%d' % (x['name'], x.get('failurePolicy'), x.get('timeoutSeconds'), len(x.get('rules',[]))))
" 2>/dev/null
done

echo ""
echo "############ C. is the webhook serving or timing out? (3 probes) ############"
for i in 1 2 3; do
  r=$(kubectl apply --dry-run=server -f - 2>&1 <<'Y' | tail -1
apiVersion: longhorn.io/v1beta2
kind: Volume
metadata: {name: webhook-probe, namespace: longhorn-system}
spec: {size: "1073741824", numberOfReplicas: 2}
Y
)
  echo "  probe$i: $(echo "$r" | cut -c1-140)"
  sleep 3
done

echo ""
echo "############ D. manager CPU burn from the loop ############"
kubectl top pods -n $NS 2>/dev/null | grep -E 'NAME|longhorn-manager' | head -10

echo ""
echo "############ E. do the manager pods show cert/CA errors? ############"
kubectl -n $NS logs -l app=longhorn-manager --tail=2000 --since=3m 2>/dev/null | grep -iE 'level=error|level=warn|fail|cert.*(expire|invalid|rotat)' | grep -v 'TLS secret' | tail -8
echo "  --- any 'not valid' / handshake errors ---"
kubectl -n $NS logs -l app=longhorn-manager --tail=3000 --since=3m 2>/dev/null | grep -icE 'handshake|not valid|expired' | sed 's/^/   count: /'
