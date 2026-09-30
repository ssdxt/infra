#!/bin/bash
echo '== GPU memory =='
nvidia-smi --query-gpu=index,memory.used,memory.total,utilization.gpu --format=csv
echo '== compute procs =='
nvidia-smi --query-compute-apps=pid,used_memory,process_name --format=csv | head -10
echo '== container GPU env =='
for c in qwen-embedding qwen-rerank img_service parser ai_server; do
  envs=$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$c" 2>/dev/null | grep -E 'CUDA_VISIBLE_DEVICES|NVIDIA_VISIBLE_DEVICES' | tr '\n' ';')
  echo "-- $c: $envs"
done
