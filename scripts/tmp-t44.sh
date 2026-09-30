#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=longhorn-system
SEC=longhorn-webhook-tls

echo "############ A. secret identity ############"
kubectl -n $NS get secret $SEC -o json 2>&1 | python3 -c "
import sys,json,base64
d=json.load(sys.stdin)
m=d['metadata']
print('  name        :', m['name'])
print('  uid         :', m['uid'])
print('  created     :', m.get('creationTimestamp'))
print('  resourceVer :', m.get('resourceVersion'))
print('  labels      :', m.get('labels'))
print('  annotations :', json.dumps(m.get('annotations'),ensure_ascii=False))
print('  ownerRefs   :', m.get('ownerReferences'))
print('  type        :', d.get('type'))
print('  data keys   :', list((d.get('data') or {}).keys()))
print('  --- managedFields (who writes) ---')
for f in m.get('managedFields',[]):
    print('   manager=%-28s op=%-8s subresource=%-6s time=%s' % (f.get('manager'), f.get('operation'), f.get('subresource'), f.get('time')))
"

echo ""
echo "############ B. certificate contents / validity ############"
kubectl -n $NS get secret $SEC -o json 2>/dev/null | python3 -c "
import sys,json,base64,subprocess
d=json.load(sys.stdin)
data=d.get('data') or {}
for k in ('tls.crt','ca.crt'):
    if k in data:
        pem=base64.b64decode(data[k]).decode()
        open('/tmp/%s.pem'%k.replace('.','_'),'w').write(pem)
        print('  ---',k,'chain length:',pem.count('BEGIN CERTIFICATE'))
"
for f in /tmp/tls_crt.pem; do
  [ -f "$f" ] && openssl x509 -in $f -noout -subject -issuer -dates -serial -fingerprint -sha256 2>&1 | sed 's/^/   /'
done

echo ""
echo "############ C. resourceVersion churn over 60s (is the object actually re-written?) ############"
prev=""
for i in $(seq 1 7); do
  rv=$(kubectl -n $NS get secret $SEC -o jsonpath='{.metadata.resourceVersion}' 2>/dev/null)
  crt=$(kubectl -n $NS get secret $SEC -o jsonpath='{.data.tls\.crt}' 2>/dev/null | md5sum | cut -c1-12)
  echo "  t=$(( (i-1)*10 ))s  resourceVersion=$rv  tls.crt-md5=$crt"
  sleep 10
done

echo ""
echo "############ D. all secrets in longhorn-system + object counts ############"
kubectl -n $NS get secrets -o custom-columns='NAME:.metadata.name,TYPE:.type,AGE:.metadata.creationTimestamp,RV:.metadata.resourceVersion' 2>&1

echo ""
echo "############ E. longhorn-manager workload ############"
kubectl -n $NS get pods -l app=longhorn-manager -o wide 2>&1
echo "  --- kind/replicas ---"
kubectl -n $NS get ds,deploy -l app=longhorn-manager 2>&1
echo "  --- leader / lease ---"
kubectl -n $NS get lease -o wide 2>&1

echo ""
echo "############ F. cert-manager involvement ############"
echo "  --- Certificate/Issuer CRs in longhorn-system ---"
kubectl -n $NS get certificate,issuer,clusterissuer 2>&1 | head -10
echo "  --- any cert-manager annotation on longhorn objects? ---"
kubectl -n $NS get secret,certificate -o json 2>/dev/null | grep -o 'cert-manager.io/[a-z-]*' | sort | uniq -c
echo "  --- cert-manager pods ---"
kubectl -n cert-manager get pods 2>&1
