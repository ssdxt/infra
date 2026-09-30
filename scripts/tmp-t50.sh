#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=longhorn-system
mkdir -p /data1/ssdxt/storage/backup

echo "############ [1] BACKUP both secrets ############"
TS=$(date +%m%d-%H%M)
BK=/data1/ssdxt/storage/backup/longhorn-webhook-secrets-$TS.yaml
kubectl -n $NS get secret longhorn-webhook-ca longhorn-webhook-tls -o yaml > $BK
ls -la $BK
echo "  --- backed up objects ---"
grep -E '^  name:' $BK
echo "  --- also save decoded certs (for rotation reference) ---"
kubectl -n $NS get secret longhorn-webhook-tls -o jsonpath='{.data.tls\.crt}' | base64 -d > /data1/ssdxt/storage/backup/longhorn-webhook-leaf-$TS.pem
kubectl -n $NS get secret longhorn-webhook-ca  -o jsonpath='{.data.tls\.crt}' | base64 -d > /data1/ssdxt/storage/backup/longhorn-webhook-ca-$TS.pem
openssl x509 -in /data1/ssdxt/storage/backup/longhorn-webhook-leaf-$TS.pem -noout -subject -dates -serial | sed 's/^/    leaf: /'
openssl x509 -in /data1/ssdxt/storage/backup/longhorn-webhook-ca-$TS.pem  -noout -subject -dates | sed 's/^/    ca  : /'

echo ""
echo "############ [2] BASELINE (before) ############"
echo "  --- ① Secret resourceVersion (2 samples / 30s) ---"
echo "     rv1=$(kubectl -n $NS get secret longhorn-webhook-tls -o jsonpath='{.metadata.resourceVersion}')  ($(date +%H:%M:%S))"
sleep 30
echo "     rv2=$(kubectl -n $NS get secret longhorn-webhook-tls -o jsonpath='{.metadata.resourceVersion}')  ($(date +%H:%M:%S))"

q() { kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- "http://localhost:9090/api/v1/query?query=$1" 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin); r=d['data']['result']
print('     %-52s -> %s' % ('$2', r[0]['value'][1] if r else 'n/a'))
" 2>/dev/null; }
echo "  --- ② secrets PUT 409 rate (5m) ---"
q 'sum(rate(apiserver_request_total%7Bresource%3D%22secrets%22%2Cverb%3D%22PUT%22%2Ccode%3D%22409%22%7D%5B5m%5D))' 'secrets PUT 409 /s'
q 'sum(rate(apiserver_request_total%7Bresource%3D%22secrets%22%2Cverb%3D%22PUT%22%2Ccode%3D%22200%22%7D%5B5m%5D))' 'secrets PUT 200 /s'
q 'sum(rate(apiserver_request_total%5B5m%5D))' 'ALL apiserver requests /s'
echo "  --- ③ inflight mutating / readOnly ---"
kubectl get --raw='/metrics' 2>/dev/null | grep '^apiserver_current_inflight_requests'
echo "  --- ④ 429 terminations increase (10m) ---"
q 'sum(increase(apiserver_request_terminations_total%7Bcode%3D%22429%22%2Cresource%3D%22secrets%22%7D%5B10m%5D))by(verb)' '429 secrets by verb (10m)'

echo "  --- ⑤ restartCount baseline (jsonpath, NOT awk AGE :) ---"
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
read A B <<< "$(rc 'app in (csi-provisioner,csi-attacher,csi-resizer,csi-snapshotter)' longhorn-system)"
echo "     CSI                restartCount=$A  crashes<15min=$B"
read C D <<< "$(rc 'io.cilium/app=operator' kube-system)"
[ -z "$C" ] && read C D <<< "$(rc 'name=cilium-operator' kube-system)"
echo "     cilium-operator    restartCount=$C  crashes<15min=$D"
kubectl -n kube-system get pods -o name 2>/dev/null | grep -i 'cilium-operator' | sed 's/^/       pod: /'
echo "     baseline at $(date +%H:%M:%S)"
