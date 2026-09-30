#!/bin/bash
echo '== docker ps -a (qwen/img/parser) =='
docker ps -a --format '{{.Names}} | {{.Status}}' | grep -E 'qwen|img_service|parser' || echo 'none of those 4 exist'
echo '== all containers =='
docker ps --format '{{.Names}}' | head -20
echo '== nvidia-persistenced service =='
systemctl status nvidia-persistenced 2>&1 | head -5
echo '== stop & disable persistenced =='
systemctl stop nvidia-persistenced 2>&1
systemctl disable nvidia-persistenced 2>&1 | tail -2
kill -9 693 2>/dev/null
sleep 2
echo '== fuser again =='
fuser -v /dev/nvidia* 2>&1 | head -5
echo '== lsmod =='
lsmod | grep nvidia || echo 'nvidia modules gone'
