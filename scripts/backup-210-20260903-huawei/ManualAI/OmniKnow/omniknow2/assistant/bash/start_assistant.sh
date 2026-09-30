#!/usr/bin/env bash
set -e

export PATH=/root/anaconda3/envs/assistant/bin:$PATH

cd /assistantspace

source /root/anaconda3/bin/activate assistant

python /assistantspace/assistant/server.py \
  2>&1 | tee -a /assistantspace/assistant/logs/assistant.log
