#!/bin/bash
echo '== A: --gpus device=0 =='
docker run --rm --gpus '"device=0"' redis:8.6.2 sh -c 'ls /dev/nvidia* 2>/dev/null' 2>&1 | head -4
echo '== B: --runtime=nvidia (legacy hook) =='
docker run --rm --runtime=nvidia -e NVIDIA_VISIBLE_DEVICES=all redis:8.6.2 sh -c 'ls /dev/nvidia* 2>/dev/null' 2>&1 | head -6
echo '== C: docker info CDI/runtimes =='
docker info 2>/dev/null | grep -iE 'cdi|runtimes|Runtimes' | head -6
echo '== D: rc-local service state =='
systemctl is-enabled rc-local 2>&1
echo '== E: /etc/cdi content =='
ls -la /etc/cdi/ 2>/dev/null
