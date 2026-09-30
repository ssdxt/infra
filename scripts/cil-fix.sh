#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== 失败 Pod 的具体错误"
kubectl describe pod cilium-2ftw7 -n kube-system 2>&1 | grep -A3 -E 'Failed|Error|Warning' | head -12
echo "=== DS 所有容器镜像（含 init）"
kubectl get ds cilium -n kube-system -o json 2>/dev/null | python3 -c '
import sys, json
d = json.load(sys.stdin)["spec"]["template"]["spec"]
for ck in ("initContainers","containers"):
    for c in d.get(ck) or []:
        print(f"  [{ck}] {c[\"name\"]}: {c[\"image\"]}")
'
echo "=== operator 镜像"
kubectl get deploy cilium-operator -n kube-system -o jsonpath='{.spec.template.spec.containers[0].image}' 2>&1; echo
echo "=== 哪个节点 NotReady"
kubectl get nodes --no-headers 2>&1 | grep -v ' Ready '
echo "=== Harbor 里 cilium 仓库实际有的 tag"
curl -sk -u admin:<HARBOR_PASSWORD> 'https://harbor.wuxing.local/v2/cilium/cilium/tags/list' 2>/dev/null | head -c 300; echo