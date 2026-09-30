#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=longhorn-system

echo "############ [3] APPLY annotations ############"
kubectl -n $NS annotate secret longhorn-webhook-ca  listener.cattle.io/static=true --overwrite 2>&1
kubectl -n $NS annotate secret longhorn-webhook-tls listener.cattle.io/static=true --overwrite 2>&1
echo "  --- verify annotations ---"
kubectl -n $NS get secret longhorn-webhook-ca longhorn-webhook-tls -o json 2>/dev/null | python3 -c "
import sys,json
for i in json.load(sys.stdin)['items']:
    print('   ', i['metadata']['name'], '-> static =', i['metadata']['annotations'].get('listener.cattle.io/static'))
"

echo ""
echo "############ [4] rolling restart longhorn-manager ############"
kubectl -n $NS rollout restart ds/longhorn-manager 2>&1
kubectl -n $NS rollout status ds/longhorn-manager --timeout=480s 2>&1 | tail -3
kubectl -n $NS get ds longhorn-manager
kubectl -n $NS get pods -l app=longhorn-manager --no-headers 2>&1 | awk '{print "   ",$1,$2,$3,$4}'

echo ""
echo "############ [5] did the annotation survive? ############"
for i in 1 2 3; do
  s=$(kubectl -n $NS get secret longhorn-webhook-ca longhorn-webhook-tls -o json 2>/dev/null | python3 -c "
import sys,json
n=0
for i in json.load(sys.stdin)['items']:
    if i['metadata']['annotations'].get('listener.cattle.io/static')=='true': n+=1
print(n)
")
  echo "  sample$i: secrets carrying static=true: $s / 2"
  sleep 10
done

echo ""
echo "############ RESULT 1: Secret resourceVersion over 60s ############"
r1=$(kubectl -n $NS get secret longhorn-webhook-tls -o jsonpath='{.metadata.resourceVersion}')
echo "  rv1=$r1  ($(date +%H:%M:%S))"
sleep 60
r2=$(kubectl -n $NS get secret longhorn-webhook-tls -o jsonpath='{.metadata.resourceVersion}')
echo "  rv2=$r2  ($(date +%H:%M:%S))"
echo "  ==> delta = $((r2-r1))  (expect 0)"

echo ""
echo "############ wait 120s for rates to settle, then results 2/3/4 ############"
sleep 120
q() { kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- "http://localhost:9090/api/v1/query?query=$1" 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin); r=d['data']['result']
print('     %-52s -> %s' % ('$2', r[0]['value'][1] if r else 'n/a'))
" 2>/dev/null; }
echo "  --- RESULT 2: secrets PUT rates (5m) ---"
q 'sum(rate(apiserver_request_total%7Bresource%3D%22secrets%22%2Cverb%3D%22PUT%22%2Ccode%3D%22409%22%7D%5B5m%5D))' 'secrets PUT 409 /s'
q 'sum(rate(apiserver_request_total%7Bresource%3D%22secrets%22%2Cverb%3D%22PUT%22%2Ccode%3D%22200%22%7D%5B5m%5D))' 'secrets PUT 200 /s'
q 'sum(rate(apiserver_request_total%7Bresource%3D%22secrets%22%2Cverb%3D%22PUT%22%7D%5B5m%5D))' 'secrets PUT all codes /s'
q 'sum(rate(apiserver_request_total%5B5m%5D))' 'ALL apiserver requests /s'
q 'sum(rate(apiserver_request_total%7Bverb%3D~%22POST%7CPUT%7CPATCH%7CDELETE%22%7D%5B5m%5D))' 'ALL write requests /s'
echo "  --- RESULT 3: inflight mutating current (3 samples) ---"
for i in 1 2 3; do kubectl get --raw='/metrics' 2>/dev/null | grep '^apiserver_current_inflight_requests'; sleep 4; done
echo "  --- RESULT 3: max_over_time 5m mutating (AFTER) ---"
q 'max_over_time(sum(apiserver_current_inflight_requests%7Brequest_kind%3D%22mutating%22%7D)%5B5m%5D)' 'AFTER max_over_time 5m mutating'
echo "  --- RESULT 4: 429 terminations ---"
q 'sum(increase(apiserver_request_terminations_total%7Bcode%3D%22429%22%2Cresource%3D%22secrets%22%7D%5B10m%5D))' '429 secrets (10m)'
q 'sum(increase(apiserver_request_terminations_total%7Bcode%3D%22429%22%7D%5B10m%5D))' '429 all resources (10m)'

echo ""
echo "############ [7] WEBHOOK functional re-verify ############"
kubectl apply --dry-run=server -f - 2>&1 <<'Y' | tail -2
apiVersion: longhorn.io/v1beta2
kind: Volume
metadata: {name: webhook-probe, namespace: longhorn-system}
spec: {size: "1073741824", numberOfReplicas: 2}
Y

echo ""
echo "############ [8] Longhorn data-plane re-verify (PVC) ############"
kubectl create ns stotest2 2>&1 | tail -1
cat <<'Y' | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata: {name: t2, namespace: stotest2}
spec:
  accessModes: ["ReadWriteOnce"]
  storageClassName: longhorn
  resources: {requests: {storage: 1Gi}}
Y
for i in $(seq 1 30); do
  ph=$(kubectl -n stotest2 get pvc t2 -o jsonpath='{.status.phase}' 2>/dev/null)
  [ "$ph" = "Bound" ] && break
  sleep 5
done
kubectl -n stotest2 get pvc t2
PH=$(kubectl -n stotest2 get pvc t2 -o jsonpath='{.status.phase}')
if [ "$PH" = "Bound" ]; then
  echo "  ==> PVC Bound OK, cleaning up"
  kubectl -n stotest2 delete pvc t2 --wait=false 2>&1
  kubectl delete ns stotest2 --wait=false 2>&1
else
  echo "  ==> PVC NOT bound (phase=$PH) - keeping for diagnosis"
fi
echo "  done at $(date +%H:%M:%S)"
