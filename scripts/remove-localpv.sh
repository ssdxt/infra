#!/bin/bash
# 卸载 OpenEBS localpv-provisioner（已确认无任何 PVC/PV 使用它）
# 回滚：helm install localpv-provisioner <chart> -n kube-system （chart 可从 Harbor/上游重新拉取）
set -e
export KUBECONFIG=/etc/kubernetes/admin.conf

echo "========== 前置检查（必须全部通过才继续）=========="
echo -n "1) 使用 openebs-hostpath 的 PVC: "
CNT=$(kubectl get pvc -A --no-headers 2>/dev/null | grep -c openebs || true)
echo "$CNT"
echo -n "2) 由 openebs 创建的 PV: "
CNT2=$(kubectl get pv --no-headers 2>/dev/null | grep -c -i openebs || true)
echo "$CNT2"
echo -n "3) helm release 是否存在: "
helm list -n kube-system 2>/dev/null | grep -c localpv-provisioner || true

if [ "${CNT:-0}" != "0" ] || [ "${CNT2:-0}" != "0" ]; then
  echo ""
  echo "!!! 检测到仍有资源在使用 openebs-hostpath，已中止删除 !!!"
  echo "    请先迁移那些 PVC 到 longhorn，再执行本脚本。"
  exit 1
fi
echo "  检查通过：没有任何东西依赖它"
echo ""

echo "========== 1. 备份当前状态 =========="
mkdir -p /data1/ssdxt/storage/backup
TS=$(date +%m%d-%H%M)
helm get values localpv-provisioner -n kube-system -o yaml > /data1/ssdxt/storage/backup/localpv-values-$TS.yaml 2>/dev/null || true
helm get manifest localpv-provisioner -n kube-system > /data1/ssdxt/storage/backup/localpv-manifest-$TS.yaml 2>/dev/null || true
kubectl get sc openebs-hostpath -o yaml > /data1/ssdxt/storage/backup/localpv-sc-$TS.yaml 2>/dev/null || true
ls -la /data1/ssdxt/storage/backup/ 2>/dev/null | grep localpv | sed 's/^/  /'
echo "  （如需回滚，用上面备份的 manifest：kubectl apply -f 该文件）"
echo ""

echo "========== 2. 卸载 helm release =========="
helm uninstall localpv-provisioner -n kube-system 2>&1 | tail -2
echo ""

echo "========== 3. 删除 StorageClass =========="
kubectl delete sc openebs-hostpath --ignore-not-found 2>&1 | tail -1
echo ""

echo "========== 4. 等待并验证 =========="
sleep 15
echo "--- localpv Pod（应为空）"
kubectl -n kube-system get pods --no-headers 2>/dev/null | grep -i localpv || echo "  ✅ 已无 localpv Pod"
echo "--- 残留资源检查"
for r in sa/localpv-provisioner deploy/localpv-provisioner clusterrole/localpv-provisioner clusterrolebinding/localpv-provisioner; do
  if kubectl get $r -n kube-system >/dev/null 2>&1 || kubectl get $r >/dev/null 2>&1; then
    echo "  ⚠️ 仍存在: $r"
  fi
done
echo "  （无输出 = 全部清理干净）"
echo "--- StorageClass（应只剩 longhorn）"
kubectl get sc 2>/dev/null | sed 's/^/  /'
echo ""
echo "--- 其他组件是否受影响（Loki 应仍在跑，因为它在 longhorn 上）"
kubectl -n logging get pods --no-headers 2>/dev/null | awk '{print "  "$1, $2, $3}'
echo ""
echo "========== 完成 =========="
echo "  收益：消除一个每 2 分钟崩溃重启的组件（148 次重启的 apiserver/journald 噪声源）"
echo "  注意：若将来重新执行 kk create cluster，localpv 可能会被再次安装（属 kk 默认组件）"
echo "        需要的话届时再执行本脚本即可。"
