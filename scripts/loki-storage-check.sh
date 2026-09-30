#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== 1. Loki 的 PVC / PV / StorageClass ====="
kubectl -n logging get pvc -o wide 2>/dev/null | sed 's/^/  /'
echo ""
PV=$(kubectl -n logging get pvc storage-loki-0 -o jsonpath='{.spec.volumeName}' 2>/dev/null)
echo "  PV: $PV"
kubectl get pv $PV -o custom-columns='NAME:.metadata.name,SC:.spec.storageClassName,CAP:.spec.capacity.storage,MODE:.spec.accessModes[*],RECLAIM:.spec.persistentVolumeReclaimPolicy,STATUS:.status.phase' --no-headers 2>/dev/null | sed 's/^/  /'
echo ""
echo "===== 2. Longhorn 卷详情（在哪台节点、几个副本、健康状态）====="
VOL=$(kubectl -n longhorn-system get volumes.longhorn.io -o name 2>/dev/null | head -1 | cut -d/ -f2)
echo "  卷名: $VOL"
kubectl -n longhorn-system get volumes.longhorn.io $VOL -o json 2>/dev/null | python3 -c '
import sys,json
d=json.load(sys.stdin)
s=d["spec"]; st=d.get("status",{})
print("    大小      :", round(int(s.get("size","0"))/1073741824,1), "GiB")
print("    副本数    :", s.get("numberOfReplicas"))
print("    前端      :", s.get("frontend"))
print("    数据位置  :", s.get("dataLocality") or "disabled(默认)")
print("    状态/健康 :", st.get("state"), "/", st.get("robustness"))
print("    当前节点  :", st.get("currentNodeID"))
print("    实际大小  :", st.get("actualSize"), "bytes")
print("    副本明细  :")
for r in (st.get("replicas") or []):
    print("      -", r.get("name"), "node=", r.get("hostId"), "state=", r.get("currentState"), "started=", r.get("started"))
'
echo ""
echo "===== 3. 卷挂在哪台节点（PV 的 node affinity / 实际挂载点）====="
kubectl get pv $PV -o jsonpath='{.spec.nodeAffinity}{"\n"}' 2>/dev/null | head -c 300; echo
NODE=$(kubectl -n logging get pod loki-0 -o jsonpath='{.spec.nodeName}' 2>/dev/null)
echo "  Loki Pod 所在节点: $NODE"
echo "  该节点上的挂载:"
ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$NODE 'df -h | grep -iE "longhorn|/var/lib/kubelet" | head -5' 2>/dev/null | sed 's/^/    /'
echo ""
echo "===== 4. 其他 PVC/PV 总览（全集群）====="
kubectl get pvc -A --no-headers 2>/dev/null | awk '{print "  "$1, $2, "->", $3, "|", $4, "|", $6}' || echo "  无"
echo ""
echo "===== 5. Longhorn 磁盘使用（各节点）====="
kubectl -n longhorn-system get nodes.longhorn.io --no-headers 2>/dev/null | awk '{print "  "$1, "就绪="$2, "可调度="$3, "allowScheduling="$4}'
echo ""
echo "===== 6. 备份/快照现状 ====="
kubectl -n longhorn-system get snapshots.longhorn.io --no-headers 2>/dev/null | head -5 | sed 's/^/  /' || echo "  无快照"
kubectl -n longhorn-system get backups.longhorn.io --no-headers 2>/dev/null | head -5 | sed 's/^/  /' || echo "  无备份（未配置 backup target）"
echo ""
echo "===== 7. Loki 保留期设置 ====="
kubectl -n logging get cm loki -o jsonpath='{.data.config\.yaml}' 2>/dev/null | grep -A2 -E 'retention_period|retention_enabled' | sed 's/^/  /'
