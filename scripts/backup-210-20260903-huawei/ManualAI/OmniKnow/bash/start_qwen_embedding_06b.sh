#!/usr/bin/env bash
set -e

export CUDA_VISIBLE_DEVICES=0

source /root/anaconda3/bin/activate ccvllm

exec vllm serve /ManualAI/OmniKnow/models/Qwen3-Embedding-0.6B \
    --runner pooling \
    --dtype auto \
    --host 0.0.0.0 \
    --port 8021 \
    --hf_overrides '{"matryoshka_dimensions":[1024]}' \
    --served-model-name qwen-embedding \
    --no-enable-prefix-caching \
    --gpu-memory-utilization 0.5 \
    --trust-remote-code \
    --max-model-len 32768 \
    2>&1 | tee -a /ManualAI/OmniKnow/logs/qwen_embedding_06b.log

echo "Qwen Embedding 0.6B vLLM 服务已启动（端口 8021）"
