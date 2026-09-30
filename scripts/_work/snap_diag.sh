#!/bin/bash
echo "########## 1. containerd 命名空间 ##########"
sudo ctr namespaces ls 2>&1

echo
echo "########## 2. moby 命名空间下的镜像 ##########"
sudo ctr -n moby images ls 2>&1 | head -20

echo
echo "########## 3. 出问题的 digest 是否作为镜像存在 ##########"
sudo ctr -n moby images ls 2>&1 | grep -i "37250a17e932" || echo "  不在 images 列表里"

echo
echo "########## 4. moby 命名空间下的 snapshots 统计 ##########"
N=$(sudo ctr -n moby snapshots ls 2>/dev/null | wc -l)
echo "  snapshot 总数: $N"
echo "--- 前 15 条 ---"
sudo ctr -n moby snapshots ls 2>&1 | head -16

echo
echo "########## 5. 找跟该 digest 相关的 snapshot key ##########"
sudo ctr -n moby snapshots ls 2>/dev/null | grep -i "37250a17e932" || echo "  key 里没有直接匹配（key 用的是 chainID，不是 layer digest）"

echo
echo "########## 6. content 里有没有这一层 ##########"
sudo ctr -n moby content ls 2>/dev/null | grep -i "37250a17e932" || echo "  content 里没有"
echo "  content 总数: $(sudo ctr -n moby content ls 2>/dev/null | wc -l)"

echo
echo "########## 7. docker 侧的镜像与存储 ##########"
sudo docker images 2>&1 | head -15
echo "--- docker system df ---"
sudo docker system df 2>&1 | head -10

echo
echo "########## 8. containerd 数据目录 ##########"
sudo du -sh /deploy/docker/containerd 2>/dev/null
sudo ls -la /deploy/docker/containerd/daemon/ 2>&1 | head -10
echo "--- snapshots 目录 ---"
sudo ls /deploy/docker/containerd/daemon/io.containerd.snapshotter.v1.overlayfs/snapshots/ 2>/dev/null | wc -l

echo
echo "########## 9. containerd 服务与日志 ##########"
systemctl is-active containerd docker 2>&1
echo "--- containerd 最近日志 ---"
journalctl -u containerd -n 20 --no-pager -o cat 2>/dev/null | tail -20
