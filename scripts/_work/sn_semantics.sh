#!/bin/bash
SOCK=/var/run/docker/containerd/containerd.sock
CTR="sudo ctr -a $SOCK -n moby snapshots --snapshotter overlayfs"

echo "########## 1. ctr snapshots 有哪些子命令 ##########"
sudo ctr snapshots --help 2>&1 | grep -A20 "COMMANDS" | head -20

echo
echo "########## 2. stat 目标 snapshot（确认 metadata 里到底在不在）##########"
echo "--- 37250a17（报 has child 的那个）---"
sudo ctr -a $SOCK -n moby snapshots --snapshotter overlayfs info sha256:37250a17e932419f4b54e624c819baf38c0025e7f9c4ba0e15af15f14a3d74c3 2>&1 | grep -v DEPRECATION | head -10
echo "--- 它的两个 children ---"
for c in sha256:1de5b7ba5cf6b91c093cb74380d418c319819ec33278fc75d02eaedef124508a sha256:72be2e4c80418e06c508bf6c14e950d53380419845eabadbf7c806ddd5c64a22; do
  echo "  --- $c ---"
  sudo ctr -a $SOCK -n moby snapshots --snapshotter overlayfs info "$c" 2>&1 | grep -v DEPRECATION | head -6
done

echo
echo "########## 3. 那两个容器在 Docker 侧还存在吗 ##########"
for id in eaa9baf7e5fe8bb5f6d7197831bd7e7e39fd7aa86e6fa2acae19c5f7e3d8d7ee 4bd3d2d6c758c98147e1859ba0897314de7fc76fdbc24806092491eb7e7b257c; do
  echo "--- ${id:0:12} ---"
  sudo docker inspect "$id" --format '  存在: {{.Name}} {{.State.Status}}' 2>&1 | head -2
  ls -d /deploy/docker/containers/${id}* 2>/dev/null | sed 's/^/  目录: /' || echo "  无目录"
done

echo
echo "########## 4. 所有容器（对照）##########"
sudo docker ps -a --format '  {{.ID}}  {{.Names}}  {{.Status}}' 2>&1

echo
echo "########## 5. containerd 里所有 container 记录 ##########"
sudo ctr -a $SOCK -n moby containers ls 2>&1 | grep -v DEPRECATION | head -10

echo
echo "########## 6. 尝试 tree（看 containerd 自己认为的层级）##########"
sudo ctr -a $SOCK -n moby snapshots --snapshotter overlayfs tree sha256:37250a17e932419f4b54e624c819baf38c0025e7f9c4ba0e15af15f14a3d74c3 2>&1 | grep -v DEPRECATION | head -30
