#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=longhorn-system; SEC=longhorn-webhook-tls

echo "############ A. raw metadata (managedFields really empty?) ############"
kubectl -n $NS get secret $SEC -o json 2>/dev/null | python3 -c "
import sys,json
m=json.load(sys.stdin)['metadata']
print(json.dumps(m,ensure_ascii=False,indent=2)[:1600])
"

echo ""
echo "############ B. RV / cert flip-flop: sample every 3s for 90s ############"
declare -A CERTC
prev_rv=""; changes=0
for i in $(seq 1 30); do
  js=$(kubectl -n $NS get secret $SEC -o json 2>/dev/null)
  rv=$(echo "$js" | python3 -c "import sys,json;print(json.load(sys.stdin)['metadata']['resourceVersion'])")
  info=$(echo "$js" | python3 -c "
import sys,json,base64,hashlib
d=json.load(sys.stdin)
crt=base64.b64decode(d['data']['tls.crt'])
import subprocess
open('/tmp/c.pem','wb').write(crt)
fp=d['metadata'].get('annotations',{}).get('listener.cattle.io/fingerprint','')
print(hashlib.md5(crt).hexdigest()[:10], fp[:24])
")
  echo "  i=$i rv=$rv  md5/fp=$info"
  CERTC[$(echo $info | awk '{print $1}')]=$(( ${CERTC[$(echo $info | awk '{print $1}')]:-0} + 1 ))
  if [ -n "$prev_rv" ] && [ "$rv" != "$prev_rv" ]; then changes=$((changes+1)); fi
  prev_rv=$rv
  sleep 3
done
echo "  --- distinct cert md5 values observed ---"
for k in "${!CERTC[@]}"; do echo "     $k  x${CERTC[$k]}"; done
echo "  --- RV delta over ~87s: from first to last ---"

echo ""
echo "############ C. CA secret stability ############"
for i in 1 2 3; do
  echo "  longhorn-webhook-ca rv=$(kubectl -n $NS get secret longhorn-webhook-ca -o jsonpath='{.metadata.resourceVersion}')"
  sleep 5
done

echo ""
echo "############ D. how many manager pods write the TLS secret? (log frequency per pod) ############"
for p in $(kubectl -n $NS get pods -l app=longhorn-manager --no-headers | awk '{print $1}'); do
  n=$(kubectl -n $NS logs $p --since=2m 2>/dev/null | grep -c 'TLS secret')
  echo "  $p : 'TLS secret' lines in last 2m = $n"
done
echo "  --- sample lines ---"
kubectl -n $NS logs -l app=longhorn-manager --tail=400 --since=2m 2>/dev/null | grep -i 'TLS secret' | head -4

echo ""
echo "############ E. which pods serve the webhooks / services ############"
kubectl -n $NS get svc longhorn-admission-webhook longhorn-conversion-webhook 2>&1
kubectl -n $NS get endpoints longhorn-admission-webhook longhorn-conversion-webhook 2>&1
kubectl -n $NS get deploy longhorn-admission-webhook longhorn-conversion-webhook 2>&1
echo "  --- validating/mutating webhook configs pointing at longhorn ---"
kubectl get validatingwebhookconfiguration,mutatingwebhookconfiguration 2>/dev/null | grep -i longhorn
kubectl get validatingwebhookconfiguration longhorn-webhook-validator -o json 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)
for w in d.get('webhooks',[]):
    c=w.get('clientConfig',{})
    print('  ',w['name'],'-> svc',c.get('service'),'caBundleLen',len(c.get('caBundle','')))
" 2>&1
