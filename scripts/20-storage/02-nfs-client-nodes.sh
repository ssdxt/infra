#!/bin/bash
# 给 11 台集群节点装 NFS 客户端（已执行过）
NODES="10.100.10.10 10.100.10.14 10.100.10.19 10.100.10.33 10.100.10.34 10.100.10.39 10.100.10.41 10.100.10.44 10.100.10.45 10.100.10.46 10.100.10.47"
for ip in $NODES; do
  ssh -o BatchMode=yes root@$ip 'dpkg -l | grep -q "^ii  nfs-common" || { apt-get update -qq; apt-get install -y -qq nfs-common; }; command -v mount.nfs' | sed "s/^/  $ip: /"
done
echo "验证: showmount -e 10.100.10.31"
