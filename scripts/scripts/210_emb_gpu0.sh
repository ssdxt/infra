#!/bin/bash
docker rm -f qwen-embedding 2>&1
docker run -d --name qwen-embedding \
  --network cc-net --network-alias qwen-embedding \
  --restart always \
  --runtime nvidia \
  -e NVIDIA_VISIBLE_DEVICES=0 \
  -e CUDA_VISIBLE_DEVICES=0 \
  -e TZ=Asia/Shanghai \
  -v /ManualAI/OmniKnow/bash:/ManualAI/OmniKnow/bash \
  -v /ManualAI/OmniKnow/logs:/ManualAI/OmniKnow/logs \
  -v /ManualAI/OmniKnow/models:/ManualAI/OmniKnow/models \
  omniknow:v2.0.0.1_05161110 \
  /bin/bash /ManualAI/OmniKnow/bash/start_qwen_embedding_06b.sh
echo "container id: $(docker ps --format '{{.ID}} {{.Names}}' | grep qwen-embedding | awk '{print $1}')"
