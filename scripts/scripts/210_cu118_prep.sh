#!/bin/bash
echo '== aliyun cu118 torch listing: cp312 wheels =='
curl -s --max-time 25 "https://mirrors.aliyun.com/pytorch-wheels/cu118/torch/" | grep -oE 'torch-2\.[0-9.]+%2Bcu118-cp312-cp312-linux_x86_64\.whl' | sort -u | tail -8
echo '== kernel headers =='
ls /usr/src/kernels/ 2>&1
ls -la /lib/modules/$(uname -r)/build 2>&1 | head -2
rpm -qa | grep -iE 'kernel-devel|kernel-headers' | head -5
echo '== fabric-manager service =='
systemctl status nvidia-fabricmanager 2>&1 | head -4
echo '== containers using nvidia runtime =='
for c in $(docker ps -q); do rt=$(docker inspect --format '{{.HostConfig.Runtime}}' $c); [ "$rt" = "nvidia" ] && echo "$(docker inspect --format '{{.Name}}' $c) -> runtime=$rt"; done
echo '== nvidia module refs =='
lsmod | grep nvidia
