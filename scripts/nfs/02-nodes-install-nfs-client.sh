#!/bin/bash
# 在 11 台集群节点上安装 NFS 客户端并验证挂载
NFS_SERVER=10.100.10.31
NFS_PATH=/data1/k8s-nfs
NODES="10.100.10.10 10.100.10.14 10.100.10.19 10.100.10.33 10.100.10.34 10.100.10.39 10.100.10.41 10.100.10.44 10.100.10.45 10.100.10.46 10.100.10.47"

echo "=== 1. 安装 nfs-common（并行）==="
for ip in $NODES; do
  (
    if ! dpkg -l 2>/dev/null | grep -q '^ii  nfs-common'; then
      ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$ip \
        'apt-get update -qq >/dev/null 2>&1; DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nfs-common >/dev/null 2>&1; command -v mount.nfs >/dev/null && echo OK || echo FAIL' 2>/dev/null \
        | xargs -I{} echo "  $ip: {}"
    else
      echo "  $ip: 已装"
    fi
  ) &
done
wait

echo ""
echo "=== 2. 验证客户端能连到 NFS 服务器 ==="
for ip in 10.100.10.10 10.100.10.33 10.100.10.47; do
  echo -n "  $ip: "
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$ip \
    "showmount -e $NFS_SERVER 2>/dev/null | tail -1" 2>/dev/null
done

echo ""
echo "=== 3. 在 control-01 上做真实挂载测试 ==="
T=/mnt/nfs-test
mkdir -p $T
if mount -t nfs $NFS_SERVER:$NFS_PATH $T 2>/dev/null; then
  echo "  挂载成功: $(df -h $T | tail -1 | awk '{print $1, $2, $4}')"
  echo "test-$(date +%s)" > $T/mount-test.txt && echo "  写入测试: 成功 ($(cat $T/mount-test.txt))"
  rm -f $T/mount-test.txt
  umount $T && echo "  已卸载测试挂载"
else
  echo "  ✗ 挂载失败"
fi
rmdir $T 2>/dev/null
echo ""
echo "=== 完成 ==="
