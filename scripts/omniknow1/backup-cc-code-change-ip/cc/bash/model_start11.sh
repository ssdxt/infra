#!/usr/bin/bash
source /root/anaconda3/bin/activate vllm-qwen3
# 设置CUDA可见设备
export CUDA_VISIBLE_DEVICES=0,1
# 启动72B大模型
vllm serve /deploy/models/Qwen-2.5-72B-Instruct-GPTQ-Int4/  --host  0.0.0.0 --port 9885  --tensor-parallel-size 2     --gpu-memory-utilization 0.6  --max-model-len 32768   --trust-remote-code  --block-size 32   --served-model-name qwen_72b  > llm_72b.log 2>&1 &


export CUDA_VISIBLE_DEVICES=1
# Embedding
vllm serve /deploy/models/bge-m3/    --host 0.0.0.0 --port 8105  --block-size 16   --api-key cc --dtype auto   --trust-remote-code   --served-model-name embed   --enable-prefix-caching    --max-model-len   8192  --task embed --disable-log-requests > embedding.log 2>&1 &


export CUDA_VISIBLE_DEVICES=1
# Rerank
vllm serve /deploy/models/bge-reranker-v2-m3/ --served-model-name bge-reranker-v2-m3 --trust-remote-code --dtype float16 --cpu-offload-gb 4 --max-model-len 8192 --api-key cc --port 8106 > rerank.log 2>&1 &
