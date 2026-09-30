#!/bin/bash
SOCK=/var/run/docker/containerd/containerd.sock
TS=$(date +%Y%m%d-%H%M%S)
BK=/deploy/backup/containerd-$TS

echo "########## 1. 备份 containerd 元数据与配置 ##########"
sudo mkdir -p $BK
sudo cp -a /deploy/docker/containerd/daemon/io.containerd.metadata.v1.bolt/meta.db $BK/ 2>&1
sudo cp -a /var/run/docker/containerd/containerd.toml $BK/ 2>&1
sudo docker images > $BK/docker-images-before.txt 2>&1
sudo ctr -a $SOCK -n moby images ls > $BK/ctr-images-before.txt 2>/dev/null
sudo ctr -a $SOCK -n moby snapshots ls > $BK/ctr-snapshots-before.txt 2>/dev/null
sudo ctr -a $SOCK -n moby content ls > $BK/ctr-content-before.txt 2>/dev/null
echo "  备份目录: $BK"
sudo ls -la $BK

echo
echo "########## 2. 删除 mis-tei:7.1.RC1 镜像（Docker 侧）##########"
sudo docker rmi -f swr.cn-south-1.myhuaweicloud.com/ascendhub/mis-tei:7.1.RC1-300I-Duo-aarch64 2>&1 | tail -5

echo
echo "########## 3. 清理 containerd 里 mis-tei 的 image 记录 ##########"
sudo ctr -a $SOCK -n moby images ls 2>/dev/null | grep -i "mis-tei" | awk '{print $1}' | while read ref; do
  echo "  删除 image: $ref"
  sudo ctr -a $SOCK -n moby images rm "$ref" 2>&1 | tail -2
done
echo "--- 剩余 mis-tei image ---"
sudo ctr -a $SOCK -n moby images ls 2>/dev/null | grep -i "mis-tei" || echo "  已清空"

echo
echo "########## 4. 清理 mis-tei 的孤儿 content ##########"
N=0
sudo ctr -a $SOCK -n moby content ls 2>/dev/null | grep "ascendhub/mis-tei" | awk '{print $1}' | sort -u | while read d; do
  if sudo ctr -a $SOCK -n moby content rm "$d" 2>/dev/null; then
    N=$((N+1))
  fi
done
echo "  已尝试清理"
echo "--- 剩余含 mis-tei label 的 content ---"
sudo ctr -a $SOCK -n moby content ls 2>/dev/null | grep -c "ascendhub/mis-tei" | sed 's/^/  条数: /'

echo
echo "########## 5. 当前 snapshots ##########"
sudo ctr -a $SOCK -n moby snapshots ls 2>/dev/null | sed 's/^/  /'

echo
echo "########## 6. docker 侧镜像 ##########"
sudo docker images 2>&1 | head -12

echo
echo "########## 7. 备份位置 ##########"
echo "  $BK"
