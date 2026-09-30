#!/bin/bash
# 在 plant02 (10.100.10.31) 上部署 NFS 服务器（已执行过，重复运行安全）
NFS_DIR=/data1/k8s-nfs
CLIENT_NET=10.100.10.0/24
apt-get install -y -qq nfs-kernel-server
mkdir -p $NFS_DIR && chmod 0777 $NFS_DIR
grep -q "$NFS_DIR" /etc/exports || echo "$NFS_DIR $CLIENT_NET(rw,sync,no_subtree_check,no_root_squash)" >> /etc/exports
exportfs -ra
systemctl enable --now nfs-server
echo "NFS 就绪: 10.100.10.31:$NFS_DIR"
exportfs -v
