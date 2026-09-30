#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "========== 1. Longhorn 功能状态 =========="
echo -n "Pod: "; kubectl -n longhorn-system get pods --no-headers 2>/dev/null | awk '{print $2, $3}' | sort | uniq -c | tr '\n' ' '; echo
echo "--- StorageClass"
kubectl get sc 2>/dev/null
echo "--- 所有 PVC"
kubectl get pvc -A --no-headers 2>/dev/null | awk '{print "  "$1, $2, $3, $4, $5, $6}'
echo "--- Longhorn 节点与磁盘"
kubectl -n longhorn-system get nodes.longhorn.io --no-headers 2>/dev/null | awk '{print "  "$1, "就绪="$2, "可调度="$3}'
echo "--- Longhorn 卷"
kubectl -n longhorn-system get volumes.longhorn.io --no-headers 2>/dev/null | awk '{print "  "$1, $2, $3, $4, $5}'
echo "--- CSI Pod 重启次数（之前会间歇崩）"
kubectl -n longhorn-system get pods --no-headers 2>/dev/null | grep -E 'csi|instance-manager' | awk '{print "  "$1, $2, "重启="$4}' | head -8
echo ""
echo "========== 2. 真实性能实测（在 Loki 现用的 Longhorn 卷上跑同步写）=========="
POD=$(kubectl -n logging get pods --no-headers 2>/dev/null | grep '^loki-0' | awk '{print $1}')
echo "  使用 Pod: $POD"
echo "--- Loki 卷挂载点"
kubectl -n logging get pod $POD -o jsonpath='{range .spec.containers[0].volumeMounts[*]}{.mountPath}{"\n"}{end}' 2>/dev/null | head -6
D=/var/loki
echo "--- 同步写测试（4k, dsync, 500 次）"
kubectl -n logging exec $POD -c loki -- sh -c "dd if=/dev/zero of=$D/ddtest bs=4k count=500 oflag=dsync 2>&1 | tail -1" 2>&1 | tail -2
echo "--- 顺序写测试（1M x 200）"
kubectl -n logging exec $POD -c loki -- sh -c "dd if=/dev/zero of=$D/ddtest2 bs=1M count=200 2>&1 | tail -1" 2>&1 | tail -2
echo "--- 顺序读测试"
kubectl -n logging exec $POD -c loki -- sh -c "dd if=$D/ddtest2 of=/dev/null bs=1M 2>&1 | tail -1" 2>&1 | tail -2
kubectl -n logging exec $POD -c loki -- sh -c "rm -f $D/ddtest $D/ddtest2" 2>/dev/null
echo ""
echo "========== 3. 结论数据汇总 =========="
echo "  （对照：etcd 要求的达标线是 同步写 ≥1000 次/秒、p99 ≤10ms）"
