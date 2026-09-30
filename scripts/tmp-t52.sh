#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=longhorn-system

q() { kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- "http://localhost:9090/api/v1/query?query=$1" 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin); r=d['data']['result']
print('     %-56s -> %s' % ('$2', r[0]['value'][1] if r else 'n/a'))
" 2>/dev/null; }
rc() { kubectl -n "$2" get pods -l "$1" -o json 2>/dev/null | python3 -c "
import sys,json,datetime
d=json.load(sys.stdin); now=datetime.datetime.now(datetime.timezone.utc)
tot=0; rec=0
for p in d['items']:
    for cs in (p['status'].get('containerStatuses') or []):
        tot+=cs.get('restartCount',0)
        t=(cs.get('lastState',{}).get('terminated') or {}).get('finishedAt')
        if t:
            dt=datetime.datetime.fromisoformat(t.replace('Z','+00:00'))
            if (now-dt).total_seconds()<900: rec+=1
print(f'{tot} {rec}')
"; }

echo "############ wait 150s so the 5m/10m windows are fully post-fix ############"
sleep 150

echo "############ CLEAN post-fix numbers ($(date +%H:%M:%S)) ############"
echo "  --- RESULT 2 (clean): secrets PUT rates over 5m ---"
q 'sum(rate(apiserver_request_total%7Bresource%3D%22secrets%22%2Cverb%3D%22PUT%22%2Ccode%3D%22409%22%7D%5B5m%5D))' 'secrets PUT 409 /s'
q 'sum(rate(apiserver_request_total%7Bresource%3D%22secrets%22%2Cverb%3D%22PUT%22%2Ccode%3D%22200%22%7D%5B5m%5D))' 'secrets PUT 200 (committed) /s'
q 'sum(rate(apiserver_request_total%7Bresource%3D%22secrets%22%2Cverb%3D%22PUT%22%7D%5B5m%5D))' 'secrets PUT all codes /s'
q 'sum(rate(apiserver_request_total%5B5m%5D))' 'ALL apiserver requests /s'
q 'sum(rate(apiserver_request_total%7Bverb%3D~%22POST%7CPUT%7CPATCH%7CDELETE%22%7D%5B5m%5D))' 'ALL write requests /s'
echo "  --- RESULT 4 (clean): 429 terminations over 5m ---"
q 'sum(increase(apiserver_request_terminations_total%7Bcode%3D%22429%22%2Cresource%3D%22secrets%22%7D%5B5m%5D))' '429 secrets (5m, post-fix)'
q 'sum(increase(apiserver_request_terminations_total%7Bcode%3D%22429%22%7D%5B5m%5D))' '429 all resources (5m, post-fix)'
echo "  --- RESULT 3: mutating queue depth, BEFORE vs AFTER (max over 5m subquery) ---"
q 'max_over_time((sum(apiserver_current_inflight_requests%7Brequest_kind%3D%22mutating%22%7D))%5B5m%3A20s%5D)' 'AFTER  max mutating depth'
NOW=$(date +%s); BEF=$((NOW-900))
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- "http://localhost:9090/api/v1/query?query=max_over_time((sum(apiserver_current_inflight_requests%7Brequest_kind%3D%22mutating%22%7D))%5B5m%3A20s%5D)&time=$BEF" 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin); r=d['data']['result']
print('     %-56s -> %s' % ('BEFORE max mutating depth (15min ago)', r[0]['value'][1] if r else 'n/a'))
" 2>/dev/null

echo ""
echo "############ RESULT 1 (recheck): RV over 60s ############"
r1=$(kubectl -n $NS get secret longhorn-webhook-tls -o jsonpath='{.metadata.resourceVersion}')
echo "  rv1=$r1 ($(date +%H:%M:%S))"; sleep 60
r2=$(kubectl -n $NS get secret longhorn-webhook-tls -o jsonpath='{.metadata.resourceVersion}')
echo "  rv2=$r2 ($(date +%H:%M:%S))  ==> delta = $((r2-r1))"

echo ""
echo "############ RESULT 5: 8-minute stability watch (restartCount) ############"
read C0 C0r <<< "$(rc 'app in (csi-provisioner,csi-attacher,csi-resizer,csi-snapshotter)' longhorn-system)"
read O0 O0r <<< "$(rc 'io.cilium/app=operator' kube-system)"
echo "  baseline $(date +%H:%M:%S): CSI restartCount=$C0 (crashes<15m=$C0r)   cilium-operator restartCount=$O0 (crashes<15m=$O0r)"
for i in $(seq 1 8); do
  sleep 60
  read C Cr <<< "$(rc 'app in (csi-provisioner,csi-attacher,csi-resizer,csi-snapshotter)' longhorn-system)"
  read O Or <<< "$(rc 'io.cilium/app=operator' kube-system)"
  echo "  t=${i}min  CSI restartCount=$C (+$((C-C0)), crashes<15m=$Cr)   cilium-operator restartCount=$O (+$((O-O0)), crashes<15m=$Or)"
done

echo ""
echo "############ final state ############"
echo "  --- rates at end of watch ($(date +%H:%M:%S)) ---"
q 'sum(rate(apiserver_request_total%7Bresource%3D%22secrets%22%2Cverb%3D%22PUT%22%2Ccode%3D%22409%22%7D%5B5m%5D))' 'secrets PUT 409 /s'
q 'sum(rate(apiserver_request_total%5B5m%5D))' 'ALL apiserver requests /s'
kubectl -n $NS get ds longhorn-manager longhorn-csi-plugin
kubectl -n $NS get pods --no-headers | awk '{print $2,$3}' | sort | uniq -c
kubectl -n $NS get pods --no-headers | grep -vE 'Running|Completed' || echo "  longhorn: none bad"
kubectl -n kube-system get pods -o name 2>/dev/null | grep cilium-operator | sed 's/^/  /'
