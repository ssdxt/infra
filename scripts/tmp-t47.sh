#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=longhorn-system; SEC=longhorn-webhook-tls

echo "############ A. how many DISTINCT leaf certs? (serial sampling, 20x3s) ############"
rm -f /tmp/serials.txt
for i in $(seq 1 20); do
  kubectl -n $NS get secret $SEC -o json 2>/dev/null | python3 -c "
import sys,json,base64,subprocess,hashlib
d=json.load(sys.stdin)
open('/tmp/x.pem','wb').write(base64.b64decode(d['data']['tls.crt']))
rv=d['metadata']['resourceVersion']
fp=d['metadata'].get('annotations',{}).get('listener.cattle.io/fingerprint','')[-12:]
ser=subprocess.run(['openssl','x509','-in','/tmp/x.pem','-noout','-serial'],capture_output=True,text=True).stdout.strip()
nb=subprocess.run(['openssl','x509','-in','/tmp/x.pem','-noout','-startdate'],capture_output=True,text=True).stdout.strip()
print(f'{rv} {fp} {ser} {nb}')
" >> /tmp/serials.txt
  sleep 3
done
echo "  distinct serials: $(awk '{print $3}' /tmp/serials.txt | sort -u | wc -l)"
awk '{print $3}' /tmp/serials.txt | sort | uniq -c | sort -rn | head
echo "  distinct fingerprints: $(awk '{print $2}' /tmp/serials.txt | sort -u | wc -l)"
awk '{print $2}' /tmp/serials.txt | sort | uniq -c | sort -rn | head
echo "  distinct notBefore:"; awk '{print $4,$5,$6,$7}' /tmp/serials.txt | sort | uniq -c
echo "  RV first/last: $(head -1 /tmp/serials.txt | awk '{print $1}') / $(tail -1 /tmp/serials.txt | awk '{print $1}')"

echo ""
echo "############ B. which manager pods hold which fingerprint (their own view) ############"
kubectl -n $NS logs -l app=longhorn-manager --tail=300 --since=90s 2>/dev/null | grep -o 'fingerprint:SHA1=[A-F0-9]*' | sort | uniq -c
echo "  --- per-pod last fingerprint ---"
for p in $(kubectl -n $NS get pods -l app=longhorn-manager --no-headers | awk '{print $1}'); do
  fp=$(kubectl -n $NS logs $p --tail=200 --since=120s 2>/dev/null | grep -o 'fingerprint:SHA1=[A-F0-9]*' | tail -1)
  cnt=$(kubectl -n $NS logs $p --tail=2000 --since=120s 2>/dev/null | grep -c 'Updating TLS secret')
  echo "   $p writes/2m=$cnt last=$fp"
done

echo ""
echo "############ C. longhorn-manager container spec (flags / env) ############"
kubectl -n $NS get ds longhorn-manager -o json 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)
c=d['spec']['template']['spec']['containers'][0]
print('  name:', c['name'])
print('  command:', c.get('command'))
print('  args:', c.get('args'))
print('  env:', [ (e.get('name'), e.get('value') or e.get('valueFrom')) for e in (c.get('env') or []) ])
print('  image:', c['image'])
print('  ports:', c.get('ports'))
"

echo ""
echo "############ D. webhook health: are webhook calls succeeding? ############"
kubectl -n kube-system logs -l component=kube-apiserver --tail=300 --since=5m 2>/dev/null | grep -iE 'longhorn.*webhook|webhook.*longhorn' | tail -5
echo "  --- try a longhorn webhook-protected action (dry-run, read-only effect) ---"
kubectl -n $NS get settings.longhorn.io default-replica-count -o jsonpath='{.value}' 2>&1; echo ""
kubectl apply --dry-run=server -f - <<'Y' 2>&1 | tail -3
apiVersion: longhorn.io/v1beta2
kind: Volume
metadata: {name: webhook-probe, namespace: longhorn-system}
spec: {size: "1073741824", numberOfReplicas: 2}
Y

echo ""
echo "############ E. etcd metrics availability + values ############"
for m in etcd_server_proposals_committed_total etcd_mvcc_db_total_size_in_bytes etcd_disk_wal_fsync_duration_seconds_bucket etcd_server_leader_changes_seen_total; do
  n=$(kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- "http://localhost:9090/api/v1/query?query=count($m)" 2>/dev/null | python3 -c "import sys,json;r=json.load(sys.stdin)['data']['result'];print(r[0]['value'][1] if r else 'n/a')" 2>/dev/null)
  echo "   $m -> series count $n"
done
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/query?query=etcd_mvcc_db_total_size_in_bytes' 2>/dev/null | head -c 400
echo ""
echo "  --- secret watchers / total watch count ---"
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/query?query=sum(apiserver_longrunning_requests%7Bresource%3D%22secrets%22%2Cverb%3D%22WATCH%22%7D)' 2>/dev/null | head -c 300
