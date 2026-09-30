#!/bin/bash
echo "########## 1. 容器列表 ##########"
sudo docker ps -a --format 'table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Image}}' | head -12

C=$(sudo docker ps --format '{{.ID}} {{.Names}}' | grep -iE "bge|tei" | head -1 | awk '{print $2}')
echo
echo "用容器: ${C:-<未找到>}"
[ -z "$C" ] && exit 0

echo
echo "########## 2. 容器完整日志 ##########"
sudo docker logs $C 2>&1 | tail -40

echo
echo "########## 3. /tmp 里的 socket 残留 ##########"
sudo docker exec $C bash -c 'ls -la /tmp/ 2>&1 | head -20'

echo
echo "########## 4. NPU 当前占用 ##########"
sudo npu-smi info 2>&1 | sed -n '1,22p'

echo
echo "########## 5. 最新 ascend plog（有没有新的错误）##########"
sudo docker exec $C bash -c '
ls -lat /root/ascend/log/debug/plog/ /root/ascend/log/run/plog/ 2>/dev/null | head -12
echo "--- 最后一个 debug plog 的错误 ---"
f=$(ls -t /root/ascend/log/debug/plog/*.log 2>/dev/null | head -1)
[ -n "$f" ] && echo "文件: $f" && grep -iE "\[ERROR\]|\[EVENT\]" "$f" 2>/dev/null | tail -15
'

echo
echo "########## 6. 内存/磁盘 ##########"
free -h | head -2
df -h /tmp /dev/shm 2>/dev/null | tail -3
