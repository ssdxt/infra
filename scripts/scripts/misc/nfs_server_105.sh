#!/bin/bash
set -x
export DEBIAN_FRONTEND=noninteractive
echo "=== [105] 安装 nfs-kernel-server ==="
apt-get update -qq 2>&1 | tail -2
apt-get install -y nfs-kernel-server 2>&1 | tail -3
echo "=== [105] 创建 /nfs 共享目录 ==="
mkdir -p /nfs
chmod 755 /nfs
echo "=== [105] 配置 /etc/exports ==="
if ! grep -q '^/nfs ' /etc/exports 2>/dev/null; then
  echo '/nfs 192.168.21.0/24(rw,sync,no_subtree_check,no_root_squash)' >> /etc/exports
fi
cat /etc/exports | grep nfs
echo "=== [105] 启用并重启 NFS 服务 ==="
exportfs -ra
systemctl enable nfs-kernel-server 2>&1 | tail -1
systemctl restart nfs-kernel-server
systemctl is-active nfs-kernel-server
echo "=== [105] 验证导出 ==="
showmount -e localhost 2>&1
echo "=== [105] 防火墙检查 ==="
ufw status 2>/dev/null | head -5 || echo "无 ufw"
