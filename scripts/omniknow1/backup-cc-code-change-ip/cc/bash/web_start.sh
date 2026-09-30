#!/usr/bin/env bash
# 统一配置入口：/deploy/deploy.env（同 api_start.sh 说明）
ENV_FILE="${ENV_FILE:-/deploy/deploy.env}"
[ -f "$ENV_FILE" ] && { set -a; source "$ENV_FILE"; set +a; }

source /root/anaconda3/bin/activate recovery
cd /deploy/code/web_0918
python https_server.py
