#!/usr/bin/env bash
set -e

cd /ManualAI/OmniKnow/omniknow2/server

source /root/anaconda3/bin/activate aiserver

python main.py 2>&1 | tee -a /ManualAI/OmniKnow/logs/aiserver.log
