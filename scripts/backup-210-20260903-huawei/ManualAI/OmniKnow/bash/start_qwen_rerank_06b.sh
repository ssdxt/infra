#!/usr/bin/env bash
set -e

export CUDA_VISIBLE_DEVICES=1

source /root/anaconda3/bin/activate ccvllm

exec vllm serve /ManualAI/OmniKnow/models/Qwen3-Reranker-0.6B \
  --dtype auto \
  --hf_overrides '{"architectures": ["Qwen3ForSequenceClassification"],"classifier_from_token": ["no", "yes"],"is_original_qwen3_reranker": true}' \
  --host 0.0.0.0 \
  --port 8022 \
  --gpu-memory-utilization 0.4 \
  --served-model-name qwen-rerank \
  --max-model-len 32768 \
  --trust-remote-code \
  --enforce-eager \
    2>&1 | tee -a /ManualAI/OmniKnow/logs/qwen_rerank_06b.log

echo "Qwen Rerank 0.6B vLLM 服务已启动（端口 8022）"

