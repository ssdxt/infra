#!/bin/bash
echo "########## 1. 关键备份：容器配置 inspect JSON ##########"
sudo ls -la /deploy/crash-recovery/ 2>&1
echo
echo "--- 各容器配置是否可读 ---"
for f in /deploy/crash-recovery/inspect-*.json; do
  [ -f "$f" ] || continue
  n=$(basename $f .json | sed 's/inspect-//')
  sz=$(sudo stat -c %s "$f" 2>/dev/null)
  img=$(sudo python3 -c "
import json,sys
try:
    d=json.load(open('$f'))[0]
    print(d['Config']['Image'])
except Exception as e:
    print('解析失败:', e)
" 2>&1)
  printf "  %-18s %6s 字节  %s\n" "$n" "$sz" "$img"
done

echo
echo "########## 2. 重置前的状态记录 ##########"
for d in /deploy/backup/containerd-reset-20260914-100423 /deploy/backup/containerd-20260914-100107; do
  echo "--- $d ---"
  sudo ls -la $d 2>&1 | head -12
done

echo
echo "########## 3. 重置前记录的容器清单 ##########"
for d in /deploy/backup/containerd-reset-20260914-100423; do
  echo "--- containers.txt ---"
  sudo cat $d/containers.txt 2>&1 | sed 's/^/  /'
  echo "--- images.txt ---"
  sudo cat $d/images.txt 2>&1 | sed 's/^/  /'
done

echo
echo "########## 4. 旧 meta.db 备份是否可用 ##########"
sudo ls -la /deploy/backup/containerd-20260914-100107/meta.db 2>&1
sudo ls -la /deploy/backup/containerd-reset-20260914-100423/meta.db 2>&1

echo
echo "########## 5. 数据卷是否完好（业务数据在 bind mount，应该没丢）##########"
echo "--- milvus ---"
sudo ls /deploy/infra/milvus/data/milvus/volumes/ 2>&1 | sed 's/^/  /'
echo "--- oceanbase ---"
sudo ls /deploy/infra/oceanbase/ 2>&1 | sed 's/^/  /'
echo "--- models ---"
sudo ls -d /deploy/models/*/ 2>&1 | sed 's/^/  /'

echo
echo "########## 6. 当前 content store（还剩什么）##########"
SOCK=/var/run/docker/containerd/containerd.sock
sudo ctr -a $SOCK -n moby content ls 2>/dev/null | sed 's/^/  /'
echo "--- content 目录大小 ---"
sudo du -sh /deploy/docker/containerd/daemon/io.containerd.content.v1.content 2>/dev/null | sed 's/^/  /'
