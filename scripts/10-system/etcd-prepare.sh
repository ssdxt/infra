#!/bin/bash
# 阶段1：三台 control 的新盘 sdb 格式化 + 挂载 + fio 验收（不碰 etcd）
export KUBECONFIG=/etc/kubernetes/admin.conf
CTRLS="10.100.10.10 10.100.10.14 10.100.10.19"
echo "===== 1. 三台 sdb 现状确认 ====="
for ip in $CTRLS; do
  echo "--- [$ip]"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=8 root@$ip '
    lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT /dev/sdb 2>/dev/null | sed "s/^/    /"
    echo -n "    已有文件系统: "; blkid /dev/sdb 2>/dev/null || echo "无（全新盘 ✓）"
    echo -n "    是否已挂载: "; mount | grep -c "/dev/sdb" || true
  ' 2>&1 | sed 's/^/  /'
done
echo ""
echo "===== 2. 格式化 xfs + 挂载到 /mnt/etcd-new ====="
for ip in $CTRLS; do
  echo -n "  [$ip] "
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$ip '
    if blkid /dev/sdb | grep -q .; then echo "已有文件系统，跳过格式化"; else mkfs.xfs -f /dev/sdb >/dev/null 2>&1 && echo "格式化完成"; fi
    mkdir -p /mnt/etcd-new
    mountpoint -q /mnt/etcd-new || mount /dev/sdb /mnt/etcd-new
    df -h /mnt/etcd-new | tail -1 | awk "{print \"  挂载: \"\$1, \$2, \"已用\"\$3, \"可用\"\$4}"
  ' 2>&1
done
echo ""
echo "===== 3. fio 验收（三台同时跑 60 秒，8k写+fdatasync，模拟 etcd）====="
for ip in $CTRLS; do
  ( ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$ip \
    "fio --name=etcd-accept --ioengine=libaio --iodepth=1 --rw=write --bs=8k --direct=0 \
        --fdatasync=1 --size=1G --filename=/mnt/etcd-new/fio.test \
        --runtime=60 --time_based --group_reporting 2>/dev/null" \
    | grep -E "write: IOPS|fdatasync|99.90th|99.99th" > /tmp/fio-$ip.txt ) &
done
wait
TOT=0
for ip in $CTRLS; do
  echo "--- [$ip]"
  cat /tmp/fio-$ip.txt | sed 's/^/    /'
  IOPS=$(grep -oP "write: IOPS=\K[0-9.]+" /tmp/fio-$ip.txt | head -1)
  P99=$(grep -A6 "fdatasync" /tmp/fio-$ip.txt | grep -oP "99.90th=\K[0-9.]+" | head -1)
  echo "    解析: IOPS=$IOPS p99.9=${P99}ms"
  PASS=$(python3 -c "print('PASS' if float('$IOPS' or 0)>=1000 and float('$P99' or 999)<=50 else 'FAIL')" 2>/dev/null)
  echo "    判定: $PASS"
  [ "$PASS" = "PASS" ] || TOT=1
done
echo ""
echo "===== 4. 清理 fio 测试文件 ====="
for ip in $CTRLS; do ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$ip "rm -f /mnt/etcd-new/fio.test" 2>/dev/null; done
if [ $TOT -eq 0 ]; then echo "=== 三台全部达标，可以进入 cutover ==="; else echo "=== 存在不达标节点，禁止迁移！==="; fi