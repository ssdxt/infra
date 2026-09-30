#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "############ A. WHY no endpoints? etcd Service + EndpointSlice detail ############"
kubectl -n kube-system get svc prometheus-stack-kube-prom-kube-etcd -o yaml 2>&1 | sed -n '1,40p'
echo "  --- endpointslice detail ---"
kubectl -n kube-system get endpointslice -o yaml 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)
for i in d['items']:
    if 'etcd' in i['metadata']['name']:
        print('  name:', i['metadata']['name'])
        print('  labels:', i['metadata'].get('labels'))
        print('  addressType:', i.get('addressType'))
        print('  endpoints:', json.dumps(i.get('endpoints'),indent=3))
        print('  ports:', json.dumps(i.get('ports'),indent=3))
"
echo "  --- do the etcd mirror pods carry the expected labels? ---"
kubectl -n kube-system get pods -l component=etcd -o wide 2>&1
kubectl -n kube-system get pods -o json 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)
for p in d['items']:
    if 'etcd' in p['metadata']['name']:
        print('  ', p['metadata']['name'], 'labels=', p['metadata']['labels'], 'podIP=', p['status'].get('podIP'), 'hostNetwork=', p['spec'].get('hostNetwork'))
"

echo ""
echo "############ B. etcd static pod manifest: full flags (listen/urls/cert-auth) ############"
ssh -o BatchMode=yes -o ConnectTimeout=6 root@10.100.10.10 "sed -n '/command:/,/image:/p' /etc/kubernetes/manifests/etcd.yaml" 2>&1 | sed 's/^/   /'

echo ""
echo "############ C. does 2381 exist anywhere? (the port the SM expects) ############"
for ip in 10.100.10.10 10.100.10.14 10.100.10.19; do
  n=$(ssh -o BatchMode=yes -o ConnectTimeout=6 root@$ip "ss -tln 2>/dev/null | grep -c ':2381'" 2>/dev/null)
  echo "   $ip : listeners on 2381 = ${n:-?}"
done

echo ""
echo "############ D. does etcd require client cert (mTLS)? ############"
ssh -o BatchMode=yes -o ConnectTimeout=6 root@10.100.10.10 "grep -E 'client-cert-auth|trusted-ca-file|cert-file|key-file' /etc/kubernetes/manifests/etcd.yaml" 2>&1 | sed 's/^/   /'

echo ""
echo "############ E. etcd client certs present on control planes? ############"
ssh -o BatchMode=yes -o ConnectTimeout=6 root@10.100.10.10 "ls -la /etc/kubernetes/pki/etcd/ 2>&1 | sed 's/^/   /'" 2>&1

echo ""
echo "############ F. what DOES the SM select? (matchLabels) ############"
kubectl -n kube-system get svc prometheus-stack-kube-prom-kube-etcd -o jsonpath='{.spec.selector}{"\n"}' 2>&1
echo "   pods in kube-system with component=etcd: $(kubectl -n kube-system get pods -l component=etcd --no-headers 2>/dev/null | wc -l)"
