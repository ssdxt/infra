#!/bin/bash
SOCK=/var/run/docker/containerd/containerd.sock
LEAF=sha256:740cab1bf82136dd24cfe80c32be6774c262239a373db1dfa1cf081e829ccd2c

echo "########## 1. 先确认这两个容器是谁（链末端挂着的）##########"
for id in eaa9baf7e5fe 4bd3d2d6c758; do
  echo "--- $id ---"
  sudo docker ps -a --filter "id=$id" --format '  {{.ID}}  {{.Names}}  {{.Status}}' 2>&1
  ls -d /deploy/docker/containers/$id* 2>/dev/null | sed 's/^/  目录: /'
done

echo
echo "########## 2. 判别实验：删一个不挂容器的叶子 snapshot ##########"
echo "  目标叶子: $LEAF"
echo "--- 用 overlayfs snapshotter 删 ---"
sudo ctr -a $SOCK -n moby snapshots --snapshotter overlayfs rm "$LEAF" 2>&1 | grep -v DEPRECATION | head -3
echo
echo "--- 删除后 ls 有没有变化 ---"
sudo ctr -a $SOCK -n moby snapshots --snapshotter overlayfs ls 2>/dev/null | wc -l | sed 's/^/  条数: /'

echo
echo "########## 3. 再试它的 parent（7.3.0 链的倒数第二层）##########"
P=sha256:c9b2c947ee3c171d5827bea32a1460eedd6e1196041c8dcd63dcc0889bc2376f
sudo ctr -a $SOCK -n moby snapshots --snapshotter overlayfs rm "$P" 2>&1 | grep -v DEPRECATION | head -3

echo
echo "########## 4. 关键的根节点测试：37250a17 ##########"
sudo ctr -a $SOCK -n moby snapshots --snapshotter overlayfs rm sha256:37250a17e932419f4b54e624c819baf38c0025e7f9c4ba0e15af15f14a3d74c3 2>&1 | grep -v DEPRECATION | head -3

echo
echo "########## 5. 再看看 ls（是否仍然只有那几条）##########"
sudo ctr -a $SOCK -n moby snapshots --snapshotter overlayfs ls 2>/dev/null | tail -n +2 | sed 's/^/  /'

echo
echo "########## 6. 磁盘目录数 ##########"
sudo ls /deploy/docker/containerd/daemon/io.containerd.snapshotter.v1.overlayfs/snapshots/ 2>/dev/null | wc -l | sed 's/^/  /'
