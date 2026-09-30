#!/bin/bash
SOCK=/var/run/docker/containerd/containerd.sock
echo "########## 0. Docker 自带 containerd 的 socket ##########"
ls -la $SOCK 2>&1
ps -ef | grep "[c]ontainerd" | head -3

echo
echo "########## 1. 命名空间 ##########"
sudo ctr -a $SOCK namespaces ls 2>&1

echo
echo "########## 2. moby 命名空间下的镜像（image store）##########"
sudo ctr -a $SOCK -n moby images ls 2>&1 | head -15

echo
echo "########## 3. 目标镜像是否在 store 里 ##########"
sudo ctr -a $SOCK -n moby images ls 2>&1 | grep -i "mis-tei" || echo "  没有 mis-tei"

echo
echo "########## 4. snapshots 总数与冲突项 ##########"
sudo ctr -a $SOCK -n moby snapshots ls 2>&1 | wc -l
echo "--- 出问题的 digest 在 snapshot key 里吗 ---"
sudo ctr -a $SOCK -n moby snapshots ls 2>&1 | grep -i "37250a17e932" || echo "  没有"

echo
echo "########## 5. containerd 里该 digest 的 content ##########"
sudo ctr -a $SOCK -n moby content ls 2>&1 | grep -i "37250a17e932" || echo "  content 里没有"

echo
echo "########## 6. 所有 snapshotter 插件 ##########"
sudo ctr -a $SOCK plugin ls 2>&1 | grep -i snapshot

echo
echo "########## 7. 真正的 snapshot 数据目录（哪个 snapshotter 在用）##########"
for d in /deploy/docker/containerd/daemon/io.containerd.snapshotter.v1.*/snapshots; do
  [ -d "$d" ] && echo "  $(dirname $d | xargs basename): $(ls $d 2>/dev/null | wc -l) 条"
done

echo
echo "########## 8. 磁盘上的 overlayfs snapshots 详情 ##########"
D=/deploy/docker/containerd/daemon/io.containerd.snapshotter.v1.overlayfs/snapshots
sudo ls -la $D 2>&1 | head -15

echo
echo "########## 9. 该 digest 在磁盘上有没有目录 ##########"
sudo find /deploy/docker/containerd -maxdepth 6 -name "*37250a17e932*" 2>/dev/null | head -5 || echo "  没找到"

echo
echo "########## 10. docker 侧该镜像的引用 ##########"
sudo docker images --digests 2>&1 | grep -i "mis-tei" || echo "  无 mis-tei"
