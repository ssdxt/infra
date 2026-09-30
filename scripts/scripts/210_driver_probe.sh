#!/bin/bash
echo '== host /ManualAI models =='
ls /ManualAI/OmniKnow/models/ 2>&1 | head -15
echo '== qwen-embedding mounts =='
docker inspect qwen-embedding 2>/dev/null | grep -A14 '"Mounts"' | head -22
echo '== rhel7 cuda repo: driver rpms available =='
curl -s --max-time 20 https://developer.download.nvidia.com/compute/cuda/repos/rhel7/x86_64/ 2>/dev/null | grep -oE 'href="[^"]*(nvidia-driver|550\.|535\.)[^"]*"' | sort -u | head -20
echo '== done =='
