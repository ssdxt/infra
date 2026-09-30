#!/bin/bash
echo '== module loaded? =='
lsmod | grep -E 'nvidia_uvm' || echo 'nvidia_uvm NOT in lsmod'
echo '== nvidia udev rules =='
ls /usr/lib/udev/rules.d/ /etc/udev/rules.d/ 2>/dev/null | grep -i nvidia
echo '--- rule content ---'
cat /usr/lib/udev/rules.d/60-nvidia.rules 2>/dev/null || cat /etc/udev/rules.d/60-nvidia.rules 2>/dev/null || echo 'no 60-nvidia.rules'
echo '== nvidia-modprobe help =='
nvidia-modprobe --help 2>&1 | head -15
echo '== try nvidia-modprobe -u =='
nvidia-modprobe -u 2>&1; sleep 1
ls -la /dev/nvidia-uvm* 2>&1
echo '== fallback: manual mknod if still missing =='
if [ ! -e /dev/nvidia-uvm ]; then mknod -m 666 /dev/nvidia-uvm c 195 253 && echo 'mknod done'; fi
ls -la /dev/nvidia-uvm* 2>&1
