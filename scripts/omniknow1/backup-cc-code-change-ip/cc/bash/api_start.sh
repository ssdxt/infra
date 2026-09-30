#!/usr/bin/bash
# ============================================================================
# 统一配置入口：所有服务地址/密钥集中在 /deploy/deploy.env（模板见 deploy.env.example）。
# set -a 使 source 进来的变量自动 export，python 侧 os.getenv 即可读到。
# 无该文件时跳过（使用代码内默认值），兼容老形态。
# ============================================================================
ENV_FILE="${ENV_FILE:-/deploy/deploy.env}"
[ -f "$ENV_FILE" ] && { set -a; source "$ENV_FILE"; set +a; }

source /root/anaconda3/bin/activate recovery
cd /deploy/code/chat_doc_0918
export ASCEND_RT_VISIBLE_DEVICES="${ASCEND_RT_VISIBLE_DEVICES_API:-0}"
python startup_obd.py --all-api > /deploy/cc/logs/api_log.txt 2>&1
