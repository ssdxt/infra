#!/bin/bash
echo "########## 1. 当前容器 ##########"
sudo docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}' | head -10

C=$(sudo docker ps --format '{{.ID}} {{.Names}}' | grep -iE "bge|tei|9f1207" | head -1 | awk '{print $2}')
[ -z "$C" ] && C=$(sudo docker ps -q | head -5 | tr '\n' ' ')
echo "候选容器: $C"

CNAME=$(sudo docker ps --format '{{.Names}}' | grep -iE "bge|tei" | head -1)
echo "用: $CNAME"

echo
echo "########## 2. 容器的环境变量（看有没有 MODEL_MEMORY_LIMIT / TEI_NPU_DEVICE）##########"
sudo docker inspect "$CNAME" --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | grep -iE "TEI|ASCEND|MODEL|HOME" | head -15

echo
echo "########## 3. 宿主 dmesg 有没有 OOM / 杀进程 ##########"
sudo dmesg -T 2>/dev/null | grep -iE "oom|killed process|out of memory" | tail -10
echo "(空=没有 OOM)"

echo
echo "########## 4. 容器内 ascend plog ##########"
sudo docker exec "$CNAME" bash -c '
for d in /root/ascend/log /home/HwHiAiUser/ascend/log /var/log/npu/slog; do
  echo "--- $d ---"
  sudo ls -la $d 2>/dev/null | head -5
done
echo "--- 找最近的 plog ---"
find / -xdev -path "*ascend*" -name "*.log" -newermt "-30 minutes" 2>/dev/null | head -10
' 2>&1 | head -30

echo
echo "########## 5. TEI python backend 自己的日志 ##########"
sudo docker exec "$CNAME" bash -c '
find / -xdev -name "*.log" -newermt "-30 minutes" 2>/dev/null | grep -viE "ascend" | head -10
echo "--- /tmp ---"
ls -la /tmp/ 2>/dev/null | head -15
' 2>&1 | head -30
