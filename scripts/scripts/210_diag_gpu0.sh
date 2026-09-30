#!/bin/bash
echo '== container state =='
docker ps -a --format '{{.Names}} | {{.Status}}' | grep qwen-embedding
echo '== recent log (error context) =='
docker logs qwen-embedding --tail 30 2>&1 | grep -B3 -A8 'NVMLError\|Error\|error' | head -30
echo '== legacy runtime inject test: NVIDIA_VISIBLE_DEVICES=0 =='
docker run --rm --runtime nvidia -e NVIDIA_VISIBLE_DEVICES=0 -v /usr/bin/nvidia-smi:/usr/bin/nvidia-smi:ro redis:8.6.2 sh -c 'nvidia-smi -L; ls /dev/nvidia* 2>/dev/null' 2>&1 | head -8
echo '== legacy runtime inject test: =1 =='
docker run --rm --runtime nvidia -e NVIDIA_VISIBLE_DEVICES=1 -v /usr/bin/nvidia-smi:/usr/bin/nvidia-smi:ro redis:8.6.2 nvidia-smi -L 2>&1 | head -4
