#!/bin/bash
export no_proxy='10.100.10.0/24,harbor.wuxing.local,localhost,127.0.0.1'
export NO_PROXY='10.100.10.0/24,harbor.wuxing.local,localhost,127.0.0.1'
echo "== WSL eth0 IP"
ip -4 addr show eth0 2>/dev/null | grep -oE 'inet [0-9.]+' || ip -4 addr | grep -oE 'inet 10\.100[0-9.]*'
echo "== 反向验证: control-01 到 WSL"
MYIP=$(ip -4 addr show eth0 2>/dev/null | grep -oE 'inet [0-9.]+' | cut -d' ' -f2 | head -1)
echo "myip=$MYIP"
echo "== 后台开始拉镜像"
nohup bash /mnt/c/Users/CC/Desktop/dsh/wsl-pull-images.sh > /home/cc/pull.log 2>&1 &
echo "pull started pid=$!"