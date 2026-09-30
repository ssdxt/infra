#!/usr/bin/env bash
set -e

# ===== 1. 初始化 conda（关键，否则 conda activate 可能失败）=====
# 根据你的实际 conda 安装路径调整
source /home/cc/miniconda3/etc/profile.d/conda.sh

# ===== 2. 激活环境 =====
conda activate /home/cc/miniconda3/envs/qwen-asr

# ===== 3. 进入工作目录 =====
cd /data/workspace/gcy/omniknow2/parser/rag

# ===== 4. 启动服务 =====
export CUDA_VISIBLE_DEVICES=0
# export LD_LIBRARY_PATH=/usr/local/cuda-12.8/lib64:$LD_LIBRARY_PATH
# export PATH=/usr/local/cuda-12.8/bin:$PATH
# export LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$LD_LIBRARY_PATH
# export LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libtinfo.so.6


nohup python api.py > logs/api.log 2>&1 &
# pipeline 模式4G
# hybird 模式10G
