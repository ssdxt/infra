#!/bin/bash
echo '== load modules =='
modprobe nvidia 2>&1
modprobe nvidia_uvm 2>&1
sleep 2
lsmod | grep nvidia
echo '== device nodes =='
ls /dev/nvidia* 2>&1
if [ ! -e /dev/nvidia-uvm ]; then mknod -m 666 /dev/nvidia-uvm c 195 253 && echo 'uvm node mknod'; fi
if [ ! -e /dev/nvidiactl ]; then mknod -m 666 /dev/nvidiactl c 195 255; fi
echo '== regen CDI =='
nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml 2>&1 | tail -2
echo "uvm in spec: $(grep -c nvidia-uvm /etc/cdi/nvidia.yaml)"
echo '== start docker =='
systemctl start docker
sleep 6
docker ps -a --format '{{.Names}} | {{.Status}}' | head -25
echo '== GPU container test =='
docker run --rm --device nvidia.com/gpu=all -v /usr/bin/nvidia-smi:/usr/bin/nvidia-smi:ro redis:8.6.2 nvidia-smi --query-gpu=index,driver_version --format=csv,noheader 2>&1 | head -3
