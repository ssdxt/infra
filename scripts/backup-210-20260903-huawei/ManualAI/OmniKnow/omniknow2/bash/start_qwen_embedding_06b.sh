#!/usr/bin/env bash
set -e

# ===== 1. 初始化 conda（关键，否则 conda activate 可能失败）=====
# 根据你的实际 conda 安装路径调整
source /root/anaconda3/etc/profile.d/conda.sh

# ===== 2. 激活环境 =====
conda activate /root/anaconda3/envs/ccvllm

# ===== 3. 进入工作目录 =====
cd /ManualAI/OmniKnow/omniknow2/parser/rag

# ===== 4. 启动 vllm embedding 服务 =====
export CUDA_VISIBLE_DEVICES=1

# --task embed \

nohup vllm serve /ManualAI/OmniKnow/models/Qwen3-Embedding-0.6B \
  --runner pooling \
  --dtype auto \
  --host 0.0.0.0 \
  --port 8021 \
  --hf_overrides '{"matryoshka_dimensions":[1024]}' \
  --served-model-name qwen-embedding \
  --no-enable-prefix-caching \
  --gpu-memory-utilization 0.5 \
  --trust-remote-code \
  --max-model-len  32768 \
  > ../logs/qwen_embedding_06b.log 2>&1 &

  # --max-model-len 8192 \

echo "Qwen Embedding 0.6B vLLM 服务已启动（端口 8021）"
