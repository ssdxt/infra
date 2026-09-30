#!/bin/bash
echo '== ccvllm env: vllm/torch/cuda wheels =='
docker exec ai_server /root/anaconda3/envs/ccvllm/bin/pip list 2>/dev/null | grep -iE '^(vllm|torch|nvidia-cuda-runtime|nvidia-cuda-nvrtc|nvidia-cudnn|nvidia-cublas|nvidia-cuda-cupti|transformers)' 
echo '== start script: embedding =='
docker exec ai_server cat /ManualAI/OmniKnow/bash/start_qwen_embedding_06b.sh 2>/dev/null | head -50
echo '== start script: rerank =='
docker exec ai_server cat /ManualAI/OmniKnow/bash/start_qwen_rerank_06b.sh 2>/dev/null | head -40
