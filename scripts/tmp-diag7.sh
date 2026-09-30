#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== v2 schema of CiliumLoadBalancerIPPool ====="
kubectl explain ciliumloadbalancerippool.spec 2>&1 | head -30
echo
echo "--- recursive ---"
kubectl explain ciliumloadbalancerippool.spec --recursive 2>&1 | head -40
echo
echo "===== blocks sub-schema ====="
kubectl explain ciliumloadbalancerippool.spec.blocks 2>&1 | head -20
echo
echo "===== CRD served versions ====="
kubectl get crd ciliumloadbalancerippools.cilium.io -o jsonpath='{range .spec.versions[*]}{.name}{" served="}{.served}{" storage="}{.storage}{"\n"}{end}'
echo
echo "===== current gateway svc state ====="
kubectl -n gateway get svc cilium-gateway-monitoring-gateway -o jsonpath='annotations={.metadata.annotations}{"\n"}spec.lbIP={.spec.loadBalancerIP}{"\n"}status={.status.loadBalancer.ingress}{"\n"}'
echo
echo "===== gateway ====="
kubectl get gateway -n gateway
echo
echo "===== ip addr 251/252/254 ====="
ip -o addr show | grep -E '10.100.10.25[0-9]' || echo "(none)"
