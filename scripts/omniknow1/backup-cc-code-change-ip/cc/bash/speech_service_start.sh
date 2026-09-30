#!/usr/bin/bash
# 统一配置入口：/deploy/deploy.env（同 api_start.sh 说明）
ENV_FILE="${ENV_FILE:-/deploy/deploy.env}"
[ -f "$ENV_FILE" ] && { set -a; source "$ENV_FILE"; set +a; }

source /root/anaconda3/bin/activate melo_tts
#source /usr/local/Ascend/ascend-toolkit/set_env.sh
#source /usr/local/Ascend/nnal/atb/set_env.sh
cd /deploy/code/melott
export NLTK_DATA=/deploy/code/melott/nltk_data/
export ASCEND_RT_VISIBLE_DEVICES="${ASCEND_RT_VISIBLE_DEVICES_SPEECH:-6}"
python web_demo_seaco.py
