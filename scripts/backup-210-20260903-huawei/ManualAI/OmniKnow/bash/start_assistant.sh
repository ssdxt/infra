#!/usr/bin/env bash
set -e

cd /ManualAI/OmniKnow/omniknow2/assistant

source /root/anaconda3/bin/activate assistant

python server.py   2>&1 | tee -a /ManualAI/OmniKnow/logs/assistant.log
