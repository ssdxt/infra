#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== A. is kube-vip actively re-adding .252/.254? ====="
for p in $(kubectl -n kube-system get pod -o name | grep kube-vip); do echo "--- $p ---"; kubectl -n kube-system logs $p --tail=120 2>&1 | grep -nE '252|254|Re-applying|Releasing' | tail -15; done
echo
echo "===== B. delete and immediately re-check (3 times) ====="
for i in 1 2 3; do
  ip addr del 10.100.10.252/32 dev ens3 2>&1; rc252=$?
  ip addr del 10.100.10.254/32 dev ens3 2>&1; rc254=$?
  echo "attempt $i: rc252=$rc252 rc254=$rc254 -> present: $(ip -o addr show ens3 | grep -cE '10.100.10.(252|254)')"
  sleep 2
done
echo "--- final ---"
ip -o addr show ens3 | grep 10.100.10.25
echo
echo "===== C. any kube-vip state objects? ====="
kubectl get cm,secret -n kube-system 2>/dev/null | grep -iE 'vip|plndr' || echo "(no kube-vip cm/secret)"
kubectl get leases -n kube-system | grep -iE 'plndr|vip' || true
echo
echo "===== D. services referencing 252/254 anywhere? ====="
kubectl get svc -A -o json | python3 -c "
import json,sys
d=json.load(sys.stdin)
for s in d['items']:
    ann=s['metadata'].get('annotations',{})
    ip=s.get('spec',{}).get('loadBalancerIP')
    ing=s.get('status',{}).get('loadBalancer',{}).get('ingress')
    if ip or ing or 'kube-vip' in str(ann):
        print(s['metadata']['namespace']+'/'+s['metadata']['name'], 'lbIP=',ip,'ingress=',ing,'ann=',{k:v for k,v in ann.items() if 'vip' in k or 'lb' in k})
"
