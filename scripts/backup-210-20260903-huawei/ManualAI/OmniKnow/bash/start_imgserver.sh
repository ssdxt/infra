#!/usr/bin/env bash
set -e

cd /ManualAI/OmniKnow/omniknow2/parser/rag

source /root/anaconda3/bin/activate parser

python img_service.py  2>&1 | tee -a  /ManualAI/OmniKnow/logs/img_service.log
