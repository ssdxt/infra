#!/bin/bash
SOCK=/var/run/docker/containerd/containerd.sock
IMG=swr.cn-south-1.myhuaweicloud.com/ascendhub/mis-tei:7.3.0-300I-Duo-aarch64

echo "########## 0. 清理前后的对照 ##########"
echo "--- oceanbase 的 content 还剩多少层（那个 32B 共享层被删了，确认影响面）---"
sudo ctr -a $SOCK -n moby content ls 2>/dev/null | grep -c "oceanbase" | sed 's/^/  oceanbase 相关 content: /'
echo "--- 当前 content 总数 ---"
sudo ctr -a $SOCK -n moby content ls 2>/dev/null | wc -l | sed 's/^/  /'
echo "--- 当前 snapshots ---"
sudo ctr -a $SOCK -n moby snapshots ls 2>/dev/null | tail -n +2 | wc -l | sed 's/^/  /'

echo
echo "########## 1. 启动 push（后台拉取镜像）##########"
sudo rm -f /tmp/pull-7330.log
nohup sudo docker pull $IMG > /tmp/pull-7330.log 2>&1 &
echo "  PID: $!"
sleep 20
echo "--- 20 秒后进度 ---"
tail -5 /tmp/pull-7330.log

echo
echo "########## 2. 观察前 3 分钟，重点看有没有再报 AlreadyExists ##########"
for i in $(seq 1 9); do
  sleep 20
  if grep -qi "already exists\|AlreadyExists" /tmp/pull-7330.log 2>/dev/null; then
    echo "  [$((i*20))s] !!! 又出现 AlreadyExists !!!"
    break
  fi
  L=$(tail -1 /tmp/pull-7330.log 2>/dev/null | tr -d '\r' | cut -c1-90)
  echo "  [$((i*20))s] $L"
  if grep -qi "Status: Downloaded\|Status: Image is up to date" /tmp/pull-7330.log 2>/dev/null; then
    echo "  >>> 拉取完成"
    break
  fi
done

echo
echo "########## 3. 当前 pull 状态 ##########"
tail -6 /tmp/pull-7330.log 2>/dev/null
echo
echo "--- 是否仍在下载 ---"
pgrep -f "docker pull $IMG" >/dev/null && echo "  仍在下载中（后台继续）" || echo "  已结束"
