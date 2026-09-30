#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== A. kube-vip.yaml FULL ====="
cat -A /etc/kubernetes/manifests/kube-vip.yaml | sed 's/\$$//' | head -80
echo
echo "===== A2. kube-vip env values (context) ====="
grep -n -A1 -E 'svc_enable|lb_enable|vip_leaseduration|vip_renewdeadline|vip_retryperiod|vip_leaderelection|vip_address|vip_interface|cp_enable|svc_election' /etc/kubernetes/manifests/kube-vip.yaml
echo
echo "===== B. kube-vip pod status ====="
kubectl -n kube-system get pod -o wide | grep -i kube-vip
echo
echo "===== C. kube-vip logs (tail 60) ====="
for p in $(kubectl -n kube-system get pod -o name | grep kube-vip); do echo "--- $p ---"; kubectl -n kube-system logs $p --tail=60 2>&1; done
echo
echo "===== D. cilium-operator logs grep gateway/lb ====="
for p in $(kubectl -n kube-system get pod -o name | grep cilium-operator); do echo "--- $p ---"; kubectl -n kube-system logs $p --tail=300 2>&1 | grep -iE 'gateway|lb.?ipam|loadbalancer|pool|error' | tail -60; done
echo
echo "===== E. cilium-operator last state (why restarts) ====="
kubectl -n kube-system get pod -o name | grep cilium-operator | while read p; do kubectl -n kube-system get $p -o jsonpath='{.metadata.name}{"\n"}{range .status.containerStatuses[*]}{.name} restarts={.restartCount} lastState={.lastState}{"\n"}{end}{"\n"}'; done
echo
echo "===== F. cilium-gateway svc yaml ====="
kubectl get svc -n gateway cilium-gateway-monitoring-gateway -o yaml
echo
echo "===== G. events in gateway ns ====="
kubectl -n gateway get events --sort-by=.lastTimestamp | tail -30
echo
echo "===== H. ExternalName services in gateway ns ====="
kubectl -n gateway get svc
