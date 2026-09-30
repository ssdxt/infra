#!/bin/bash
echo "########## 1. 服务状态 ##########"
echo "  docker    : $(systemctl is-active docker 2>&1)"
echo "  containerd(系统): $(systemctl is-active containerd 2>&1)"
pgrep -f "containerd --config /var/run/docker" >/dev/null && echo "  Docker自带containerd: 运行中" || echo "  Docker自带containerd: 未运行"

echo
echo "########## 2. meta.db 是否还在 ##########"
sudo ls -la /deploy/docker/containerd/daemon/io.containerd.metadata.v1.bolt/ 2>&1

echo
echo "########## 3. overlayfs snapshotter 数据目录 ##########"
sudo ls /deploy/docker/containerd/daemon/io.containerd.snapshotter.v1.overlayfs/snapshots/ 2>&1 | head -10
echo "  目录数: $(sudo ls /deploy/docker/containerd/daemon/io.containerd.snapshotter.v1.overlayfs/snapshots/ 2>/dev/null | wc -l)"

echo
echo "########## 4. 我的备份脚本执行痕迹 ##########"
sudo ls -dt /deploy/backup/containerd-* 2>/dev/null | head -3

echo
echo "########## 5. 容器目录（Docker 侧的容器定义）##########"
echo "  容器目录数: $(sudo ls /deploy/docker/containers/ 2>/dev/null | wc -l)"
sudo ls -la /deploy/docker/containers/ 2>&1 | head -10

echo
echo "########## 6. docker ps -a ##########"
sudo docker ps -a --format '  {{.ID}}  {{.Names}}  {{.Status}}' 2>&1

echo
echo "########## 7. docker images ##########"
sudo docker images 2>&1 | head -10

echo
echo "########## 8. containerd 里的 content / snapshots / images ##########"
SOCK=/var/run/docker/containerd/containerd.sock
echo "  content : $(sudo ctr -a $SOCK -n moby content ls 2>/dev/null | wc -l)"
echo "  snapshots: $(sudo ctr -a $SOCK -n moby snapshots ls 2>/dev/null | tail -n +2 | wc -l)"
echo "  images  : $(sudo ctr -a $SOCK -n moby images ls 2>/dev/null | tail -n +2 | wc -l)"

echo
echo "########## 9. docker 服务日志（最近 15 行）##########"
journalctl -u docker -n 15 --no-pager -o cat 2>/dev/null | tail -15

echo
echo "########## 10. 报错（如果有）##########"
sudo docker ps -a 2>&1 | grep -i error | head -5
