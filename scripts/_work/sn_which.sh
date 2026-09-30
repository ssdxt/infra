#!/bin/bash
SOCK=/var/run/docker/containerd/containerd.sock
TARGET=sha256:37250a17e932419f4b54e624c819baf38c0025e7f9c4ba0e15af15f14a3d74c3

echo "########## 1. containerd 配置里默认用哪个 snapshotter ##########"
sudo cat /var/run/docker/containerd/containerd.toml 2>&1 | grep -vE "^\s*#" | grep -vE "^\s*$"

echo
echo "########## 2. 逐个 snapshotter 查 snapshots ##########"
for sn in overlayfs erofs native blockfile; do
  echo "===== snapshotter: $sn ====="
  out=$(sudo ctr -a $SOCK -n moby snapshots --snapshotter $sn ls 2>&1)
  if echo "$out" | grep -qi "not found\|unknown\|skip"; then
    echo "  不可用"
  else
    cnt=$(echo "$out" | tail -n +2 | grep -c . )
    echo "  条数: $cnt"
    echo "$out" | tail -n +2 | head -12 | sed 's/^/    /'
  fi
  echo
done

echo "########## 3. 目标 chainID 在哪个 snapshotter 里存在 ##########"
for sn in overlayfs erofs native; do
  if sudo ctr -a $SOCK -n moby snapshots --snapshotter $sn ls 2>/dev/null | grep -q "$TARGET"; then
    echo "  >>> 在 $sn 里找到了！"
  fi
done
echo "  (无输出=都没找到)"

echo
echo "########## 4. 磁盘上各 snapshotter 的数据目录 ##########"
for d in /deploy/docker/containerd/daemon/io.containerd.snapshotter.v1.*; do
  n=$(basename $d)
  if [ -d "$d/snapshots" ]; then
    echo "  $n/snapshots: $(sudo ls $d/snapshots 2>/dev/null | wc -l) 条"
  else
    echo "  $n: 无 snapshots 子目录 ($(sudo ls $d 2>/dev/null | tr '\n' ' '))"
  fi
done

echo
echo "########## 5. erofs snapshotter 的数据目录详情 ##########"
D=/deploy/docker/containerd/daemon/io.containerd.snapshotter.v1.erofs
sudo ls -la $D 2>&1 | head -10

echo
echo "########## 6. 试着直接删掉那个幽灵 snapshot ##########"
for sn in overlayfs erofs native; do
  echo "--- $sn ---"
  sudo ctr -a $SOCK -n moby snapshots --snapshotter $sn rm "$TARGET" 2>&1 | head -3
done
