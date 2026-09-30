#!/bin/bash
echo '== modprobe nvidia-uvm =='
modprobe nvidia-uvm 2>&1 && echo 'modprobe ok' || echo 'modprobe FAILED'
sleep 1
echo '== host dev after =='
ls /dev/nvidia* 2>&1
echo '== persist module =='
mkdir -p /etc/modules-load.d
grep -qxF 'nvidia-uvm' /etc/modules-load.d/nvidia-uvm.conf 2>/dev/null || echo 'nvidia-uvm' >> /etc/modules-load.d/nvidia-uvm.conf
cat /etc/modules-load.d/nvidia-uvm.conf
echo '== regenerate CDI =='
nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml 2>&1 | tail -3
echo '== uvm in yaml? =='
grep -c 'nvidia-uvm' /etc/cdi/nvidia.yaml
echo '== container device test =='
docker run --rm --device nvidia.com/gpu=all redis:8.6.2 sh -c 'ls /dev/nvidia* 2>/dev/null'
