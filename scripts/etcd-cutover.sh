#!/bin/bash
# etcd 滚动迁移到 /dev/sdb（逐台，失败自动回滚）
# 注意：fio 验收未达 1000 IOPS 基线（实测 ~400，p99.9 54-64ms），用户知情并指示继续。
set -u
export KUBECONFIG=/etc/kubernetes/admin.conf
CTRLS="10.100.10.10 10.100.10.14 10.100.10.19"
TS=$(date +%m%d-%H%M)
CACERT=/etc/kubernetes/pki/etcd/ca.crt
CERT=/etc/kubernetes/pki/etcd/client.crt
KEY=/etc/kubernetes/pki/etcd/client.key

health() { # $1=ip
  etcdctl --cacert=$CACERT --cert=$CERT --key=$KEY --endpoints=https://$1:2379 \
    endpoint health 2>/dev/null | grep -q "is healthy"
}
all_healthy() {
  local bad=0
  for ip in $CTRLS; do health $ip || bad=1; done
  return $bad
}

echo "########## 0. 全局快照（迁移前保险）##########"
SNAP=/root/etcd-snap-$TS.db
ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@10.100.10.10 \
  "etcdctl --cacert=$CACERT --cert=$CERT --key=$KEY --endpoints=https://10.100.10.10:2379 \
   snapshot save $SNAP >/dev/null 2>&1 && etcdctl --cacert=$CACERT --cert=$CERT --key=$KEY snapshot status $SNAP 2>/dev/null | head -1" \
  | sed 's/^/  /'
scp -o BatchMode=yes -o StrictHostKeyChecking=no root@10.100.10.10:$SNAP /tmp/snap-copy.db >/dev/null 2>&1
for ip in 10.100.10.14 10.100.10.19; do
  scp -o BatchMode=yes -o StrictHostKeyChecking=no /tmp/snap-copy.db root@$ip:$SNAP >/dev/null 2>&1
done
echo "  快照已分发到三台 /root/etcd-snap-$TS.db"
echo ""

NODE=0
FAILED=""
for ip in $CTRLS; do
  NODE=$((NODE+1))
  echo "############################################################"
  echo "### 节点 $NODE/3 : $ip"
  echo "############################################################"
  # 迁移前：确认另外两台健康（保证 quorum）
  OTHERS=$(echo $CTRLS | tr ' ' '\n' | grep -v "^$ip$" | tr '\n' ' ')
  OKCNT=0
  for o in $OTHERS; do health $o && OKCNT=$((OKCNT+1)); done
  if [ $OKCNT -lt 2 ]; then echo "  ⛔ 其余成员不足 2 台健康，中止整批迁移"; FAILED=$ip; break; fi
  echo "  其余成员健康: $OKCNT/2 ✓"

  ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$ip "bash -s" -- "$ip" "$TS" <<'REMOTE'
set -u
ip=$1; ts=$2
MNT=/mnt/etcd-new; DATA=/var/lib/etcd
rollback() {
  echo "  ↩️ 回滚 $ip ..."
  systemctl stop etcd 2>/dev/null
  mountpoint -q $DATA && umount $DATA
  [ -d $DATA ] && rm -rf $DATA
  [ -d $DATA.old-$ts ] && mv $DATA.old-$ts $DATA
  sed -i "\|/var/lib/etcd|d" /etc/fstab
  systemctl start etcd; sleep 8
  systemctl is-active etcd
}
echo "  [1] 备份数据目录 → /root/etcd-data-bak-$ts.tar.gz"
tar czf /root/etcd-data-bak-$ts.tar.gz -C /var/lib/etcd . 2>/dev/null && echo "      备份完成 $(du -sh /root/etcd-data-bak-$ts.tar.gz | cut -f1)"
echo "  [2] 停止 etcd"
systemctl stop etcd && echo "      已停止"
echo "  [3] .10 专属清理：卸载重复挂载点"
if [ "$ip" = "10.100.10.10" ]; then
  mountpoint -q /mnt/etcd-new && umount /mnt/etcd-new
  mountpoint -q /data2 && { umount /data2 && echo "      /data2 已卸载"; }
  sed -i "\|/data2|d" /etc/fstab && echo "      fstab 中 /data2 行已清除"
fi
echo "  [4] 数据拷贝到新盘"
mkdir -p $MNT
mount /dev/sdb $MNT 2>/dev/null
rsync -a $DATA/ $MNT/ 2>/dev/null || cp -a $DATA/. $MNT/
echo "      拷贝完成: $(du -sh $MNT | cut -f1)"
umount $MNT
echo "  [5] 切换挂载点 → $DATA"
mv $DATA $DATA.old-$ts
mkdir -p $DATA
mount /dev/sdb $DATA
[ -d $DATA/member ] && echo "      数据确认在位: $(du -sh $DATA | cut -f1)" || { echo "      ❌ 数据缺失！回滚"; rollback; exit 1; }
UUID=$(blkid -s UUID -o value /dev/sdb)
sed -i "\|/var/lib/etcd|d" /etc/fstab
echo "UUID=$UUID  /var/lib/etcd  xfs  defaults,noatime  0 2" >> /etc/fstab
mkdir -p /etc/systemd/system/etcd.service.d
printf "[Unit]\nRequiresMountsFor=/var/lib/etcd\n" > /etc/systemd/system/etcd.service.d/require-mount.conf
systemctl daemon-reload
echo "  [6] 启动 etcd"
systemctl start etcd
OK=0
for i in $(seq 1 12); do
  sleep 5
  if etcdctl --cacert=/etc/kubernetes/pki/etcd/ca.crt --cert=/etc/kubernetes/pki/etcd/client.crt \
       --key=/etc/kubernetes/pki/etcd/client.key --endpoints=https://$ip:2379 \
       endpoint health 2>/dev/null | grep -q "is healthy"; then OK=1; break; fi
done
if [ $OK -eq 1 ]; then
  echo "      ✅ etcd 在新盘上健康 (等待 $((i*5))s)"
  df -h $DATA | tail -1 | sed "s/^/      /"
else
  echo "      ❌ 60 秒未恢复健康 → 自动回滚"
  rollback
  exit 1
fi
REMOTE
  RC=$?
  sleep 5
  if [ $RC -ne 0 ]; then
    echo "  ⛔ 节点 $ip 迁移失败（已回滚），中止剩余节点。失败节点: $ip $FAILED"
    FAILED="$FAILED $ip"
    break
  fi
  # 三成员整体健康确认
  ALLBAD=0
  for c in $CTRLS; do health $c || ALLBAD=1; done
  if [ $ALLBAD -ne 0 ]; then
    echo "  ⛔ 全集群成员健康检查未通过，中止"
    FAILED="$FAILED $ip"
    break
  fi
  echo "  ✅ 节点 $ip 迁移成功，三成员健康"
  echo ""
done

echo ""
echo "########## 最终验证 ##########"
for ip in $CTRLS; do
  echo -n "  [$ip] "
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$ip \
    "systemctl is-active etcd | tr '\n' ' '; mount | grep '/var/lib/etcd' | head -1 | awk '{print \"挂载于\"\$1}'; etcdctl --cacert=/etc/kubernetes/pki/etcd/ca.crt --cert=/etc/kubernetes/pki/etcd/client.crt --key=/etc/kubernetes/pki/etcd/client.key --endpoints=https://$ip:2379 endpoint status 2>/dev/null | awk '{print \"DB=\"\$4\" leaders=\"\$5\" raftIndex=\"\$6}'" 2>/dev/null
done
echo ""
echo -n "  kubectl 集群状态: "
kubectl get nodes --no-headers 2>/dev/null | awk '{c++; if($2=="Ready") r++} END{print r"/"c" Ready"}'
echo -n "  kubectl get ns 数量: "
kubectl get ns --no-headers 2>/dev/null | wc -l
echo -n "  Loki/Longhorn 冒烟: "
kubectl -n logging get pod loki-0 -o jsonpath='{.status.phase}' 2>/dev/null; echo -n " / "
kubectl -n longhorn-system get pods --no-headers 2>/dev/null | grep -c Running; echo ""
echo ""
if [ -z "$FAILED" ]; then echo "=== 全部三台迁移成功 ==="; else echo "=== 迁移中止，失败/未处理节点: $FAILED ==="; fi