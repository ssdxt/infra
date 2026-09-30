#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "========== 1. localpv 现状 =========="
kubectl -n kube-system get pods --no-headers 2>/dev/null | grep -i localpv | awk '{print "  Pod:", $1, "就绪:", $2, "状态:", $3, "重启:", $4}'
kubectl -n kube-system get deploy localpv-provisioner -o jsonpath='{.spec.template.spec.containers[0].image} {.spec.template.spec.containers[0].command} {.spec.template.spec.containers[0].args}' 2>/dev/null; echo
echo "--- 崩溃原因（最后几行）"
P=$(kubectl -n kube-system get pods --no-headers 2>/dev/null | grep localpv | head -1 | awk '{print $1}')
kubectl -n kube-system logs "$P" --tail=5 2>&1 | tail -4
echo ""
echo "========== 2. 有没有东西在用 openebs-hostpath =========="
echo "--- 所有 PVC（含 StorageClass）"
kubectl get pvc -A --no-headers 2>/dev/null | awk '{print "  "$1, $2, $3, $6}' || echo "  无 PVC"
echo "--- 所有 PV"
kubectl get pv --no-headers 2>/dev/null | awk '{print "  "$1, $2, $3, $5, $6}' || echo "  无 PV"
echo "--- 引用 openebs 的工作负载"
kubectl get pods -A -o json 2>/dev/null | python3 -c '
import sys, json
d = json.load(sys.stdin)
hits = []
for p in d["items"]:
    for v in p["spec"].get("volumes", []) or []:
        if (v.get("persistentVolumeClaim")):
            hits.append((p["metadata"]["namespace"], p["metadata"]["name"], v["persistentVolumeClaim"]["claimName"]))
print("  挂载 PVC 的 Pod:", hits if hits else "无")
'
echo ""
echo "========== 3. 它是怎么部署的（决定怎么删/怎么改）=========="
echo "--- helm release"
helm list -A 2>/dev/null | grep -i -E 'openebs|localpv|NAME' | head -3
echo "--- kube-system 里的 openebs 相关对象"
kubectl -n kube-system get all,sa,role,rolebinding --no-headers 2>/dev/null | grep -i -E 'openebs|localpv' | head -10
echo "--- 集群级 openebs 对象"
kubectl get clusterrole,clusterrolebinding --no-headers 2>/dev/null | grep -i -E 'openebs|localpv' | head -6
echo "--- StorageClass"
kubectl get sc 2>/dev/null
echo "--- openebs 相关 Namespace"
kubectl get ns --no-headers 2>/dev/null | grep -i openebs || echo "  无 openebs 命名空间（说明装在 kube-system）"
echo ""
echo "========== 4. localpv 是否支持 --leader-election=false（关了就不崩）=========="
echo "  （查镜像里的二进制支持的参数）"
NODE=$(kubectl -n kube-system get pods --no-headers 2>/dev/null | grep localpv | head -1 | awk '{print $1}' | xargs -I{} kubectl -n kube-system get pod {} -o jsonpath='{.spec.nodeName}' 2>/dev/null)
echo "  所在节点: $NODE"
timeout 30 ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$NODE 'crictl ps -a 2>/dev/null | grep localpv | head -2' 2>/dev/null
echo ""
echo "--- localpv 用的数据目录（看它落在哪块盘）"
timeout 20 ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$NODE 'ls -ld /var/openebs/local 2>/dev/null; df -h /var/openebs/local 2>/dev/null | tail -1' 2>/dev/null