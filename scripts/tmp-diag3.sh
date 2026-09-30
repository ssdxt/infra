#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== 1. create test-lb (no loadBalancerIP, no pool) ====="
kubectl delete svc test-lb -n default --ignore-not-found >/dev/null 2>&1
kubectl create svc loadbalancer test-lb --tcp=80:80 --dry-run=client -o yaml | kubectl apply -f -
sleep 20
echo "--- test-lb ingress after 20s ---"
kubectl get svc test-lb -o jsonpath='{.status.loadBalancer.ingress}'; echo
kubectl get svc test-lb
echo
echo "===== 2. create test-lb-static with explicit loadBalancerIP 10.100.10.252 ====="
kubectl delete svc test-lb-static -n default --ignore-not-found >/dev/null 2>&1
kubectl create svc loadbalancer test-lb-static --tcp=80:80 --dry-run=client -o yaml > /tmp/tls.yaml
python3 - <<'PY'
import re
p='/tmp/tls.yaml'
s=open(p).read()
s=s.replace('  type: LoadBalancer','  loadBalancerIP: 10.100.10.252\n  type: LoadBalancer')
open(p,'w').write(s)
PY
kubectl apply -f /tmp/tls.yaml
sleep 25
echo "--- test-lb-static ingress after 25s ---"
kubectl get svc test-lb-static -o jsonpath='{.status.loadBalancer.ingress}'; echo
kubectl get svc test-lb-static
echo
echo "===== 3. LB-IPAM service with annotation lbipam.cilium.io/ips ====="
kubectl delete svc test-lb-ann -n default --ignore-not-found >/dev/null 2>&1
kubectl create svc loadbalancer test-lb-ann --tcp=80:80 --dry-run=client -o yaml > /tmp/tla.yaml
python3 - <<'PY'
p='/tmp/tla.yaml'
s=open(p).read()
s=s.replace('  type: LoadBalancer','  type: LoadBalancer\n  # annotation test')
s=s.replace('metadata:\n  creationTimestamp: null\n  labels:\n    app: test-lb-ann','metadata:\n  annotations:\n    lbipam.cilium.io/ips: 10.100.10.253\n  creationTimestamp: null\n  labels:\n    app: test-lb-ann')
open(p,'w').write(s)
PY
cat /tmp/tla.yaml
kubectl apply -f /tmp/tla.yaml
sleep 20
echo "--- test-lb-ann ingress after 20s ---"
kubectl get svc test-lb-ann -o jsonpath='{.status.loadBalancer.ingress}'; echo
echo
echo "===== 4. CRDs available ====="
kubectl get crd | grep -iE 'ciliumloadbalancerippool|ciliuml2announcementpolicy|ciliumbgp'
echo
echo "===== 5. cilium-config full (lb/svc/l2 related) ====="
kubectl -n kube-system get cm cilium-config -o jsonpath='{.data}' | tr ',' '\n' | grep -iE 'l2|lb-|loadbalancer|external-ip|ipam' || true
echo
echo "===== 6. cilium service-ipam / svc source ====="
kubectl -n kube-system get cm cilium-config -o yaml | grep -nE 'l2-announcements|enable-l2|external-ip|svc-source|nodeport' || echo "(none)"
echo
echo "===== 7. kube-vip reference doc chapter 2 ====="
ls -l /data1/ssdxt/集群改造详细命令记录.md 2>&1
grep -n -iE 'kube-vip|svc_enable|vip_pool|LoadBalancer' /data1/ssdxt/集群改造详细命令记录.md 2>/dev/null | head -40
echo
echo "===== 8. apiserver health (why operators restart) ====="
kubectl -n kube-system get pod -l component=etcd -o wide 2>/dev/null
df -h /var/lib/etcd 2>/dev/null | tail -2
uptime
echo
echo "===== 9. cleanup temps ====="
kubectl delete svc test-lb test-lb-ann -n default --ignore-not-found
echo "(test-lb-static kept for now)"
