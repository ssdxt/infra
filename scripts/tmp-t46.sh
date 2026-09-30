#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=longhorn-system; SEC=longhorn-webhook-tls

echo "############ A. capture BOTH cert variants and compare ############"
rm -f /tmp/certA.pem /tmp/certB.pem /tmp/map.txt
for i in $(seq 1 60); do
  kubectl -n $NS get secret $SEC -o json 2>/dev/null | python3 -c "
import sys,json,base64,hashlib
d=json.load(sys.stdin)
crt=base64.b64decode(d['data']['tls.crt'])
fp=d['metadata'].get('annotations',{}).get('listener.cattle.io/fingerprint','')
h=hashlib.md5(crt).hexdigest()[:10]
open('/tmp/%s.pem'%h,'wb').write(crt)
print(h, fp)
" >> /tmp/map.txt
  have=$(ls /tmp/*.pem 2>/dev/null | wc -l)
  [ "$have" -ge 2 ] && break
  sleep 2
done
sort /tmp/map.txt | uniq -c | sort -rn | head -4
echo "  --- variants captured ---"
for f in /tmp/*.pem; do
  case "$f" in /tmp/tls_crt.pem|/tmp/c.pem) continue;; esac
  echo "  ==== $f ===="
  openssl x509 -in $f -noout -subject -issuer -dates -serial 2>&1 | sed 's/^/     /'
  echo -n "     SANs: "; openssl x509 -in $f -noout -ext subjectAltName 2>/dev/null | tail -1 | sed 's/^ *//'
done

echo ""
echo "############ B. is the CA in the webhook caBundle the same as longhorn-webhook-ca? ############"
kubectl -n $NS get secret longhorn-webhook-ca -o jsonpath='{.data.tls\.crt}' 2>/dev/null | base64 -d > /tmp/ca.pem
openssl x509 -in /tmp/ca.pem -noout -subject -dates 2>&1 | sed 's/^/   ca: /'
echo -n "   ca sha256: "; openssl x509 -in /tmp/ca.pem -noout -fingerprint -sha256 2>/dev/null | sed 's/.*=//'
echo "   --- leaf chain issuer (from variant A) ---"
openssl x509 -in $(ls /tmp/*.pem | grep -v -E 'ca.pem|tls_crt.pem|c.pem' | head -1) -noout -issuer 2>&1 | sed 's/^/   /'
echo "   --- does leaf chain include the CA? ---"
grep -c 'BEGIN CERTIFICATE' $(ls /tmp/*.pem | grep -v -E 'ca.pem|tls_crt.pem|c.pem' | head -1)

echo ""
echo "############ C. Prometheus quantification ############"
q() { kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- wget -qO- "http://localhost:9090/api/v1/query?query=$1" 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)
r=d['data']['result']
print('   %-58s -> %s' % ('$2', r[0]['value'][1] if r else 'n/a'))
" 2>/dev/null; }
q 'sum(increase(apiserver_request_total%7Bresource%3D%22secrets%22%2Cverb%3D%22PUT%22%2Ccode%3D%22409%22%7D%5B10m%5D))' 'secrets PUT 409 (conflicts) last 10m'
q 'sum(increase(apiserver_request_total%7Bresource%3D%22secrets%22%2Cverb%3D%22PUT%22%2Ccode%3D%22200%22%7D%5B10m%5D))' 'secrets PUT 200 (committed) last 10m'
q 'sum(rate(apiserver_request_total%7Bresource%3D%22secrets%22%2Cverb%3D%22PUT%22%7D%5B10m%5D))' 'secrets PUTs/s (all codes)'
q 'sum(rate(etcd_server_proposals_committed_total%5B10m%5D))' 'etcd proposals committed /s (total writes)'
q 'sum(rate(apiserver_request_total%7Bverb%3D~%22POST%7CPUT%7CPATCH%7CDELETE%22%7D%5B10m%5D))' 'apiserver write requests /s (all resources)'
q 'sum(rate(etcd_mvcc_db_total_size_in_bytes%5B10m%5D))' 'etcd db growth B/s'
q 'histogram_quantile(0.99,sum(rate(etcd_disk_wal_fsync_duration_seconds_bucket%5B5m%5D))by(le,instance))' 'etcd WAL fsync p99 (s)'
q 'histogram_quantile(0.99,sum(rate(etcd_disk_backend_commit_duration_seconds_bucket%5B5m%5D))by(le,instance))' 'etcd backend commit p99 (s)'
q 'sum(apiserver_registered_watchers%7Bresource%3D%22secrets%22%7D)' 'secret WATCHers (fan-out multiplier)'
q 'max_over_time(etcd_server_leader_changes_seen_total%5B1h%5D)' 'etcd leader changes seen'

echo ""
echo "############ D. Longhorn webhook/cert settings + chart toggles ############"
kubectl -n $NS get settings.longhorn.io 2>/dev/null | grep -iE 'webhook|tls|cert' || echo "   no webhook/tls/cert settings in settings.longhorn.io"
echo "   --- longhorn-manager DS args ---"
kubectl -n $NS get ds longhorn-manager -o jsonpath='{.spec.template.spec.containers[0].args}' 2>&1
echo ""
echo "   --- chart values mentioning webhook ---"
helm show values /data1/ssdxt/charts/longhorn-1.7.2.tgz 2>/dev/null | grep -n -i -B2 -A4 'webhook' | head -30
