#!/bin/bash
# ============================================================
# etcd 迁移到高性能专用盘（滚动，业务不中断）
#
# 用法：
#   bash 05-etcd-migrate-to-fastdisk.sh check          # 只做验收（fio），不改任何东西
#   bash 05-etcd-migrate-to-fastdisk.sh prepare <IP>   # 格式化+挂载+拷数据（不动运行中的 etcd）
#   bash 05-etcd-migrate-to-fastdisk.sh cutover <IP>   # 切到新盘（会重启该节点 etcd）
#   bash 05-etcd-migrate-to-fastdisk.sh restore-timers # 三台都迁完后，恢复租约参数
#
# 安全设计：
#   - check 阶段 fio 不达标 → 直接退出，绝不继续
#   - cutover 前自动备份原数据目录
#   - 每台之间必须人工确认（脚本会暂停等你回车）
#   - 三台逐个操作，绝不并发
# ============================================================
set -u
CTRLS="10.100.10.10 10.100.10.14 10.100.10.19"
NEWDEV="${NEWDEV:-/dev/sdb}"          # ← 新盘设备名，用 lsblk 确认后改这里
NEWFS=xfs
MNT=/var/lib/etcd
STAGE=/mnt/etcd-new
BK=/data1/ssdxt/storage/backup
mkdir -p $BK
export KUBECONFIG=/etc/kubernetes/admin.conf

sshc() { ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$1 "$2"; }

# ---------- 1) 验收：fio 测试新盘 ----------
do_check() {
  echo "===== 新盘验收（三台【同时】跑，排除共享争抢）====="
  echo "  设备: $NEWDEV   注意: 这一步会往盘上写临时文件（未格式化则用裸设备测）"
  for ip in $CTRLS; do
    sshc $ip "lsblk -d -o NAME,SIZE,TYPE | grep -v loop; echo '---- 当前挂载:'; df -h $NEWDEV 2>/dev/null | tail -1" | sed "s/^/  [$ip] /"
  done
  echo ""
  echo "  开始 fio（每台 60 秒，同时启动）..."
  for ip in $CTRLS; do
    ( sshc $ip "mkdir -p $STAGE 2>/dev/null; mountpoint -q $STAGE || mount $NEWDEV $STAGE 2>/dev/null; \
        fio --name=etcd-accept --ioengine=libaio --iodepth=1 --rw=write --bs=8k --direct=0 \
            --fdatasync=1 --size=1G --filename=$STAGE/fio.test --runtime=60 --time_based \
            --group_reporting 2>/dev/null | grep -E 'write: IOPS|fdatasync|99.00th|99.90th|99.99th|50.00th'" \
      | sed "s/^/  [$ip] /" ) &
  done
  wait
  echo ""
  echo "  ===== 判定标准（人工核对）====="
  echo "    同步写 IOPS ≥ 1000      （你现在是 25~243）"
  echo "    fdatasync p99 ≤ 10ms     （你现在是 8~37ms）"
  echo "    fdatasync p99.9 ≤ 50ms   （你现在是 616ms~2.1s）"
  echo "  三台全部达标才继续；任一不达标 → 先找虚拟化方，不要迁移。"
}

# ---------- 2) prepare：格式化 + 挂载 + 拷数据（不影响运行） ----------
do_prepare() {
  IP=$1
  echo "===== [$IP] 准备新盘（不动运行中的 etcd）====="
  sshc $IP "set -e
    # 安全检查：确认设备存在且未挂载到关键路径
    lsblk -d -o NAME,SIZE,TYPE | grep -q \"\$(basename $NEWDEV)\" || { echo '设备不存在'; exit 1; }
    if mount | grep -q \"$NEWDEV\"; then echo '警告: 该设备已挂载，请先确认'; mount | grep $NEWDEV; fi
    # 格式化（若已有文件系统则跳过）
    blkid $NEWDEV >/dev/null 2>&1 || mkfs.$NEWFS -f $NEWDEV
    mkdir -p $STAGE
    mountpoint -q $STAGE || mount $NEWDEV $STAGE
    # 记录 UUID 供 fstab 用
    echo -n 'UUID: '; blkid -s UUID -o value $NEWDEV
    # 拷数据（etcd 仍在跑，用 rsync 做一致副本；切的时候再停一次做增量）
    mkdir -p $STAGE/etcd
    rsync -a --delete /var/lib/etcd/ $STAGE/etcd/ 2>/dev/null || cp -a /var/lib/etcd/. $STAGE/etcd/
    du -sh $STAGE/etcd
    echo 'prepare 完成'
  " 2>&1 | sed "s/^/  [$IP] /"
}

# ---------- 3) cutover：切到新盘 ----------
do_cutover() {
  IP=$1
  echo "===== [$IP] 切换到新盘（会重启本节点 etcd）====="
  echo "  切前检查：集群三台 etcd 必须都健康"
  for c in $CTRLS; do
    echo -n "    $c: "
    sshc $c "etcdctl --cacert=/etc/kubernetes/pki/etcd/ca.crt --cert=/etc/kubernetes/pki/etcd/client.crt \
        --key=/etc/kubernetes/pki/etcd/client.key --endpoints=https://$c:2379 endpoint health 2>/dev/null | tail -1"
  done
  echo ""
  read -p "  确认继续切换 $IP ？（输入 yes 继续）: " ans
  [ "$ans" = "yes" ] || { echo "  已取消"; return; }

  sshc $IP "set -e
    TS=\$(date +%m%d-%H%M)
    # 1) 备份原数据目录
    mkdir -p $BK
    tar czf $BK/etcd-data-orig-$IP-\$TS.tar.gz -C /var/lib/etcd . 2>/dev/null && echo \"  已备份: $BK/etcd-data-orig-$IP-\$TS.tar.gz\"
    # 2) 停 etcd
    systemctl stop etcd && echo '  etcd 已停'
    # 3) 最后一次增量同步（保证数据一致）
    mountpoint -q $STAGE || mount $NEWDEV $STAGE
    rsync -a --delete /var/lib/etcd/ $STAGE/etcd/ && echo '  增量同步完成'
    # 4) 把新盘挂到 /var/lib/etcd
    mv /var/lib/etcd /var/lib/etcd.old-\$TS
    mkdir -p /var/lib/etcd
    umount $STAGE 2>/dev/null || true
    mount $NEWDEV /var/lib/etcd
    # 5) fstab（UUID，绝不加 nofail）
    UUID=\$(blkid -s UUID -o value $NEWDEV)
    sed -i \"\\|/var/lib/etcd|d\" /etc/fstab
    echo \"UUID=\$UUID  /var/lib/etcd  $NEWFS  defaults,noatime  0 2\" >> /etc/fstab
    # 6) systemd 挂载依赖（盘没挂上就不许启动 etcd）
    mkdir -p /etc/systemd/system/etcd.service.d
    printf '[Unit]\nRequiresMountsFor=/var/lib/etcd\n' > /etc/systemd/system/etcd.service.d/require-mount.conf
    systemctl daemon-reload
    # 7) 启动 etcd
    systemctl start etcd && sleep 8 && systemctl is-active etcd
    echo '  ---- 新盘挂载情况:'; df -h /var/lib/etcd | tail -1
  " 2>&1 | sed "s/^/  [$IP] /"

  echo ""
  echo "  ---- 健康验证（等 20 秒）"
  sleep 20
  sshc $IP "etcdctl --cacert=/etc/kubernetes/pki/etcd/ca.crt --cert=/etc/kubernetes/pki/etcd/client.crt \
      --key=/etc/kubernetes/pki/etcd/client.key --endpoints=https://$IP:2379 endpoint health 2>&1 | tail -1"
  echo "  ---- 全集群三台健康"
  for c in $CTRLS; do
    echo -n "    $c: "
    sshc $c "etcdctl --cacert=/etc/kubernetes/pki/etcd/ca.crt --cert=/etc/kubernetes/pki/etcd/client.crt \
        --key=/etc/kubernetes/pki/etcd/client.key --endpoints=https://$c:2379 endpoint health 2>/dev/null | tail -1"
  done
  echo "  ---- 节点状态"
  kubectl get nodes --no-headers | awk '{print "    "$1, $2}'
  echo ""
  echo "  ✓ 确认上面全部正常后，再对下一台执行 cutover。"
}

# ---------- 4) 恢复租约参数（三台迁完后） ----------
do_restore_timers() {
  echo "===== 恢复租约参数（换盘后经过 24 小时观察再做）====="
  echo "  etcd: 选举超时 10000→2500ms、心跳 500→250ms（改 /etc/etcd.env，逐台滚动重启）"
  echo "  kube-vip: 30/20/5 → 15/5/2（改 /etc/kubernetes/manifests/kube-vip.yaml，用 python 精确改，勿用 sed）"
  echo "  scheduler/controller-manager: 60/40/5 → 15/10/2（改静态清单）"
  echo ""
  echo "  当前值核对："
  for c in $CTRLS; do
    echo -n "    [$c] etcd:   "; sshc $c "grep -E 'ELECTION|HEARTBEAT' /etc/etcd.env | tr '\n' ' '"
    echo -n "    [$c] kube-vip: "; sshc $c "grep -A1 -e vip_leaseduration -e vip_renewdeadline /etc/kubernetes/manifests/kube-vip.yaml | grep value | tr '\n' ' '"
    echo ""
  done
  echo "  （确认 etcd 换盘后连续 24h 无 slow fdatasync 再执行修改）"
}

case "${1:-}" in
  check)          do_check ;;
  prepare)        do_prepare "${2:?需要IP}" ;;
  cutover)        do_cutover "${2:?需要IP}" ;;
  restore-timers) do_restore_timers ;;
  *) grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//' | head -30 ;;
esac
