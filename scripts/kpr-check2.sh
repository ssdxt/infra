#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== helm values 里的 k8sService 设置"
helm get values cilium -n kube-system -o yaml 2>/dev/null | grep -iE 'k8sService|kubeProxyReplacement' 
echo "=== ConfigMap 所有 k8s/service 相关键"
kubectl get cm cilium-config -n kube-system -o json 2>/dev/null | python3 -c '
import sys, json
d = json.load(sys.stdin)["data"]
for k in sorted(d):
    if "k8s-service" in k or "kube-proxy" in k or "k8sService" in k:
        print("  ", k, "=", repr(d[k]))
'
echo "=== DS 是否有 ConfigMap checksum 注解（决定改CM是否触发滚动）"
kubectl get ds cilium -n kube-system -o jsonpath='{.spec.template.metadata.annotations}' 2>&1 | head -c 300; echo