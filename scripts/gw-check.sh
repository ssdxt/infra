#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "=== operator 日志里 gateway 相关"
kubectl logs -n kube-system -l io.cilium/app=operator --tail=300 2>/dev/null | grep -iE 'gateway|forbidden|rbac|error' | tail -10
echo "=== RBAC: cilium-operator ClusterRole 是否含 gatewayclasses"
kubectl get clusterrole cilium-operator -o json 2>/dev/null | python3 -c '
import sys, json
d = json.load(sys.stdin)
found = False
for r in d.get("rules", []):
    grp = r.get("apiGroups", [])
    res = r.get("resources", [])
    if any("gateway" in x for x in grp) or any("gatewayclass" in x for x in res):
        print("rule:", grp, res, r.get("verbs"))
        found = True
if not found:
    print("NO gateway RBAC rules found")
'
echo "=== GatewayClass 完整对象"
kubectl get gatewayclass cilium -o yaml 2>/dev/null | grep -vE '^\s*(creationTimestamp|resourceVersion|uid|generation):' | head -25