#!/bin/bash
SOCK=/var/run/docker/containerd/containerd.sock
TS=$(date +%Y%m%d-%H%M%S)
BK=/deploy/backup/containerd-reset-$TS

echo "########## 1. 记录当前全部状态（用于恢复）##########"
sudo mkdir -p $BK
sudo docker ps -a --format '{{.ID}}|{{.Names}}|{{.Image}}|{{.Status}}' > $BK/containers.txt 2>&1
sudo docker images --format '{{.Repository}}:{{.Tag}}|{{.ID}}|{{.Size}}' > $BK/images.txt 2>&1
sudo ctr -a $SOCK -n moby content ls > $BK/content.txt 2>/dev/null
sudo ctr -a $SOCK -n moby snapshots ls > $BK/snapshots.txt 2>/dev/null
sudo cp -a /deploy/docker/containerd/daemon/io.containerd.metadata.v1.bolt/meta.db $BK/ 2>&1
echo "  备份目录: $BK"
echo "--- 容器清单 ---"
cat $BK/containers.txt | sed 's/^/  /'
echo "--- 镜像清单 ---"
cat $BK/images.txt | sed 's/^/  /'

echo
echo "########## 2. 停止 Docker（containerd 会一起停）##########"
systemctl stop docker docker.socket 2>&1
sleep 5
echo "  docker: $(systemctl is-active docker)"
pgrep -f "containerd --config /var/run/docker" >/dev/null && echo "  containerd 仍在运行" || echo "  containerd 已停止"

echo
echo "########## 3. 重置 metadata（保留 content，不重新下载）##########"
echo "--- 重置前 ---"
sudo du -sh /deploy/docker/containerd/daemon/io.containerd.metadata.v1.bolt 2>/dev/null | sed 's/^/  /'
sudo du -sh /deploy/docker/containerd/daemon/io.containerd.content.v1.content 2>/dev/null | sed 's/^/  /'

echo "--- 删除 bolt 元数据 ---"
sudo rm -f /deploy/docker/containerd/daemon/io.containerd.metadata.v1.bolt/meta.db
echo "  已删除 meta.db"

echo "--- 清空 overlayfs snapshotter 的残留数据 ---"
SD=/deploy/docker/containerd/daemon/io.containerd.snapshotter.v1.overlayfs
sudo ls $SD/snapshots 2>/dev/null | wc -l | sed 's/^/  删除前目录数: /'
sudo rm -rf $SD/snapshots/* 2>/dev/null
sudo rm -rf $SD/metadata.db 2>/dev/null
echo "  已清空"

echo
echo "########## 4. 启动 Docker ##########"
systemctl start docker 2>&1
sleep 15
echo "  docker: $(systemctl is-active docker)"
echo "--- docker info ---"
sudo docker info 2>/dev/null | grep -E "Storage Driver|Root Dir"

echo
echo "########## 5. 重置后的状态 ##########"
echo "--- snapshots ---"
sudo ctr -a $SOCK -n moby snapshots ls 2>/dev/null | tail -n +2 | wc -l | sed 's/^/  条数: /'
echo "--- content（应保留）---"
sudo ctr -a $SOCK -n moby content ls 2>/dev/null | wc -l | sed 's/^/  条数: /'
echo "--- images（预期为空）---"
sudo ctr -a $SOCK -n moby images ls 2>/dev/null | tail -n +2 | wc -l | sed 's/^/  条数: /'
echo "--- docker images ---"
sudo docker images 2>&1 | head -5
echo "--- docker ps -a ---"
sudo docker ps -a --format '  {{.Names}}  {{.Status}}' 2>&1 | head -8

echo
echo "########## 6. 备份位置 ##########"
echo "  $BK"
