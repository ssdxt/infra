#!/usr/bin/env bash
set -e

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

# nohup vllm serve /mnt/ddata2/models/Qwen3-Reranker-4B \
# --gpu-memory-utilization 0.5 \
# --task "score" \

nohup vllm serve /ManualAI/OmniKnow/models/Qwen3-Reranker-0.6B \
  --dtype auto \
  --hf_overrides '{"architectures": ["Qwen3ForSequenceClassification"],"classifier_from_token": ["no", "yes"],"is_original_qwen3_reranker": true}' \
  --host 0.0.0.0 \
  --port 8022 \
  --gpu-memory-utilization 0.4 \
  --served-model-name qwen-rerank \
  --max-model-len 32768 \
  --trust-remote-code \
  --enforce-eager  > ../logs/qwen_rerank_06b.log 2>&1 &


echo "Qwen Rerank 0.6B vLLM 服务已启动（端口 8022）"

