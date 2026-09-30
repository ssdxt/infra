#!/bin/bash
echo '== nvidia-runtime containers before =='
for c in $(docker ps -q); do rt=$(docker inspect --format '{{.HostConfig.Runtime}}' "$c"); [ "$rt" = "nvidia" ] && echo "$(docker inspect --format '{{.Name}}' "$c")"; done
echo '== set restart=no then stop =='
docker update --restart=no qwen-embedding qwen-rerank img_service parser
docker stop qwen-embedding qwen-rerank img_service parser
sleep 3
echo '== verify stopped =='
docker ps -a --format '{{.Names}} | {{.Status}}' | grep -E 'qwen|img_service|parser'
echo '== lsmod nvidia =='
lsmod | grep nvidia || echo 'nvidia modules gone'
echo '== host gpu procs =='
nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader 2>&1 | head -5
echo '== fuser on nvidia devs =='
fuser -v /dev/nvidia* 2>&1 | head -5
