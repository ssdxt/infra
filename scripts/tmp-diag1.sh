#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== 1. GATEWAY YAML (status part) ====="
kubectl get gateway -n gateway -o yaml
echo
echo "===== 2. SERVICES matching gateway/lb ====="
kubectl get svc -A -o wide | grep -iE 'cilium-gateway|NAMESPACE|LoadBalancer' || true
echo
echo "===== 3. KUBE-VIP MANIFEST grep ====="
grep -nE 'svc_enable|lb_enable|vip_leaseduration|vip_renewdeadline|vip_retryperiod|vip_leaderelection' /etc/kubernetes/manifests/kube-vip.yaml || true
echo
echo "===== 4. CILIUM VERSION / CONFIG ====="
kubectl -n kube-system get pods -o wide | grep -iE 'cilium|NAME'
echo
echo "===== 5. CILIUM LB IPAM POOLS ====="
kubectl get ciliumloadbalancerippool 2>&1 || true
echo
echo "===== 6. GATEWAYCLASS ====="
kubectl get gatewayclass
echo
echo "===== 7. HTTPROUTE ====="
kubectl get httproute -A
echo
echo "===== 8. CILIUMCONFIG LB RELATED ====="
kubectl -n kube-system get cm cilium-config -o yaml 2>/dev/null | grep -iE 'enable-lb|lb-ipam|l2-announce|gateway-api|kube-proxy' || true
echo
echo "===== 9. IP POOL / node ips ====="
kubectl get nodes -o wide
