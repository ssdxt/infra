#!/bin/bash
set -x
export DEBIAN_FRONTEND=noninteractive
echo "=== [98] 安装 nfs-common 客户端 ==="
apt-get update -qq 2>&1 | tail -2
apt-get install -y nfs-common 2>&1 | tail -3
echo "=== [98] 创建本地挂载点 /nfs ==="
mkdir -p /nfs
echo "=== [98] 挂载 105:/nfs ==="
mount -t nfs 192.168.21.105:/nfs /nfs
echo "=== [98] 挂载结果 ==="
df -h /nfs
echo "=== [98] 写入 fstab 持久化 ==="
if ! grep -q '192.168.21.105:/nfs' /etc/fstab 2>/dev/null; then
  echo '192.168.21.105:/nfs /nfs nfs rw,soft,timeo=50,retrans=2,noatime,_netdev 0 0' >> /etc/fstab
fi
grep '105:/nfs' /etc/fstab
echo "=== [98] 读写验证 ==="
echo "nfs-test-$(date +%s) from 98" > /nfs/.write_test_98 && cat /nfs/.write_test_98 && rm -f /nfs/.write_test_98 && echo "读写验证OK"
