#!/usr/bin/bash
source /root/anaconda3/bin/activate vllm-qwen3

CUDA_VISIBLE_DEVICES=0,1 vllm serve /deploy/models/Qwen-2.5-72B-Instruct-GPTQ-Int4/ \
  --host 0.0.0.0 --port 9885 \
  --gpu-memory-utilization 0.8 \
  --tensor-parallel-size 2 \
  --max-model-len 32768 \
  --trust-remote-code \
  --block-size 32 \
  --served-model-name qwen_72b > /deploy/cc/logs/llm_72b.log 2>&1 &
echo $! > /deploy/cc/model_main.pid

CUDA_VISIBLE_DEVICES=1 vllm serve /deploy/models/bge-m3/ \
  --host 0.0.0.0 --port 8105 \
  --block-size 16 --api-key cc \
  --dtype auto --trust-remote-code \
  --served-model-name embed \
  --enable-prefix-caching \
  --max-model-len 8192 \
  --task embed \
  --disable-log-requests > /deploy/cc/logs/embedding.log 2>&1 &
echo $! >> /deploy/cc/model_main.pid

CUDA_VISIBLE_DEVICES=1 vllm serve /deploy/models/bge-reranker-v2-m3/ \
  --served-model-name bge-reranker-v2-m3 \
  --trust-remote-code --dtype float16 \
  --cpu-offload-gb 4 --max-model-len 8192 \
  --api-key cc --port 8106 > /deploy/cc/logs/rerank.log 2>&1 &
echo $! >>  /deploy/cc/model_main.pid
