#!/bin/bash
OUT=/deploy/crash-recovery

echo "########## 1. Docker 存储驱动与 layerdb 实际路径 ##########"
sudo docker info 2>/dev/null | grep -iE "Storage Driver|Root Dir|Backing|containerd"
echo "--- /deploy/docker/image/ ---"
sudo ls -la /deploy/docker/image/ 2>&1
echo "--- 找 layerdb/mounts ---"
sudo find /deploy/docker -maxdepth 4 -type d -name "mounts" 2>/dev/null | head -5
sudo find /deploy/docker -maxdepth 3 -type d -name "layerdb" 2>/dev/null | head -5

echo
echo "########## 2. 所有容器的挂载（确认数据在宿主机）##########"
for f in $OUT/inspect-*.json; do
  n=$(basename $f .json | sed 's/inspect-//')
  echo "===== $n ====="
  sudo python3 -c "
import json,sys
d=json.load(open('$f'))[0]
for m in d.get('Mounts',[]):
    print('  %-40s -> %-40s (%s)' % (m.get('Source'), m.get('Destination'), m.get('Type')))
" 2>/dev/null || sudo grep -o '"Source":"[^"]*"' $f | head -5
done

echo
echo "########## 3. 数据目录是否完好 ##########"
echo "--- milvus ---"
sudo ls -la /deploy/infra/milvus/data/milvus/volumes/ 2>&1 | head -6
echo "--- oceanbase ---"
sudo ls -la /deploy/oceanbase/ 2>&1 | head -8
echo "--- models ---"
sudo ls -d /deploy/models/*/ 2>&1 | head -8

echo
echo "########## 4. 尝试删除一个容器（milvus-etcd，风险最低）##########"
sudo docker rm -f milvus-etcd 2>&1 | tail -3
echo "删除后:"
sudo docker ps -a --format 'table {{.Names}}\t{{.Status}}' | head -8
