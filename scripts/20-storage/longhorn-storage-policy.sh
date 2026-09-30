#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== 1. Longhorn 全局空间策略设置 ====="
for s in storage-over-provisioning-percentage storage-minimal-available-percentage storage-reserved-percentage-for-other-components default-replica-count; do
  echo -n "  $s = "
  kubectl -n longhorn-system get settings.longhorn.io $s -o jsonpath='{.value}' 2>/dev/null || echo "（无此设置项）"
  echo ""
done
echo ""
echo "===== 2. 各节点磁盘的 Longhorn 视角（/data1 磁盘）====="
kubectl -n longhorn-system get nodes.longhorn.io -o json 2>/dev/null | python3 -c '
import sys, json
d = json.load(sys.stdin)
for n in d["items"]:
    name = n["metadata"]["name"]
    for dk, dv in (n.get("spec", {}).get("disks") or {}).items():
        lines = dv.get("diskPath") or dk
        st = (n.get("status", {}).get("diskStatus", {}) or {}).get(dk, {})
        print("  %-14s disk=%-18s StorageReserved=%s  最大=%sGB  可用=%sGB" % (
            name, dv.get("path"), 
            round(int(dv.get("storageReserved", 0))/1024**3, 1),
            round(int(st.get("storageMaximum", 0))/1024**3, 1),
            round(int(st.get("storageAvailable", 0))/1024**3, 1)))
' 2>/dev/null | head -10
echo ""
echo "===== 3. 实际使用（Longhorn 副本占了多少）====="
ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@10.100.10.44 'du -sh /data1/longhorn 2>/dev/null; df -h /data1 | tail -1' 2>/dev/null | sed 's/^/  /'
echo ""
echo "===== 4. UI 里的调整入口对照 ====="
echo "  UI: Node → 选节点 → Edit Node and Disks → 每块盘的 Storage Reserved / Scheduling / Tags"
echo "  UI: Settings → storage-over-provisioning-percentage / storage-minimal-available-percentage"
echo "  kubectl: kubectl -n longhorn-system edit nodes.longhorn.io wxq-run-06"