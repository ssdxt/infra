#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== 1. 所有 gateway 相关 CRD（按 group 分组）"
kubectl get crd -o custom-columns='NAME:.metadata.name,GROUP:.spec.group,VERSIONS:.spec.versions[*].name' 2>/dev/null | grep -iE 'NAME|gateway'
echo ""
echo "=== 2. ValidatingAdmissionPolicy / Binding（safe-upgrades）"
kubectl get validatingadmissionpolicy,validatingadmissionpolicybinding 2>/dev/null | head -6
echo ""
echo "=== 3. 当前有没有 Gateway / GatewayClass / HTTPRoute 对象"
kubectl get gatewayclass 2>&1
kubectl get gateway -A 2>&1
kubectl get httproute -A 2>&1
kubectl get grpcroute,tlsroute,tcproute,udproute,backendtlspolicy,referencegrant -A 2>&1 | head -8
echo ""
echo "=== 4. Cilium 认为哪些 CRD 是必需/可选的（operator 日志）"
kubectl logs -n kube-system -l io.cilium/app=operator --tail=400 2>/dev/null | grep -E 'Required GatewayAPI|Checking for required' | tail -2