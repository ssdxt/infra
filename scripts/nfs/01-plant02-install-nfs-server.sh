#!/bin/bash
# 在 plant02 (10.100.10.31) 上部署 NFS 服务器，供 K8s 集群共享存储使用
set -e
NFS_DIR=/data1/k8s-nfs
CLIENT_NET=10.100.10.0/24

echo "=== [1/5] 安装 nfs-kernel-server ==="
if ! dpkg -l 2>/dev/null | grep -q '^ii  nfs-kernel-server'; then
  apt-get update -qq 2>/dev/null || true
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nfs-kernel-server 2>&1 | tail -2
else
  echo "  已安装"
fi

echo "=== [2/5] 创建导出目录 ==="
mkdir -p $NFS_DIR
# 权限：让 K8s 里的 Pod 能以任意 UID 写入（NFS 默认 root_squash 会挡住 root 之外的写入）
chmod 0777 $NFS_DIR
echo "  目录: $NFS_DIR ($(df -h $NFS_DIR | tail -1 | awk '{print $4}') 可用)"

echo "=== [3/5] 配置 /etc/exports ==="
# no_root_squash: 允许 Pod 以 root 写入；sync: 数据同步落盘（安全优先）
if ! grep -q "$NFS_DIR" /etc/exports 2>/dev/null; then
  echo "$NFS_DIR $CLIENT_NET(rw,sync,no_subtree_check,no_root_squash)" >> /etc/exports
  echo "  已添加导出规则"
else
  echo "  规则已存在"
fi
exportfs -ra
echo "  当前导出:"; exportfs -v | sed 's/^/    /'

echo "=== [4/5] 启动并设置开机自启 ==="
systemctl enable nfs-server >/dev/null 2>&1
systemctl restart nfs-server
systemctl is-active nfs-server && echo "  nfs-server 运行中"
systemctl is-active rpcbind 2>/dev/null || systemctl start rpcbind

echo "=== [5/5] 本机验证 ==="
showmount -e localhost 2>/dev/null || showmount -e 127.0.0.1
echo ""
echo "=== NFS 服务器就绪：10.100.10.31:$NFS_DIR ==="
