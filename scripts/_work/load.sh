#!/bin/bash
echo "########## 1. 谁在吃 CPU ##########"
ps aux --sort=-%cpu 2>/dev/null | head -18

echo
echo "########## 2. 负载 / 进程数 ##########"
uptime
echo "进程总数: $(ps -e --no-headers | wc -l)"

echo
echo "########## 3. NPU 上的进程 ##########"
sudo npu-smi info 2>&1 | sed -n '/Process id/,$p'

echo
echo "########## 4. 各容器 CPU/内存占用 ##########"
sudo docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}' 2>&1 | head -10

echo
echo "########## 5. glm-4 容器（systemd 镜像）在干什么 ##########"
PID=$(sudo docker inspect glm-4-9b-chat --format '{{.State.Pid}}' 2>/dev/null)
echo "host PID: $PID"
sudo ps -ef --forest -g $(sudo ps -o pgid= -p $PID 2>/dev/null | tr -d ' ') 2>/dev/null | head -25

echo
echo "########## 6. glm-4 容器内进程 ##########"
sudo docker exec glm-4-9b-chat ps -ef 2>&1 | head -25

echo
echo "########## 7. dmesg 最近的告警 ##########"
sudo dmesg -T 2>/dev/null | tail -15
