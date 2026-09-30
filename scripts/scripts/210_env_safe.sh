#!/bin/bash
echo '== env.safe 配置定义 =='
grep -nB3 -A10 'safe' /ManualAI/OmniKnow/omniknow2/server/core/config.py 2>/dev/null | grep -vE '__pycache__|\.venv' | head -25
echo '== .env 里 ENV_ 键 =='
grep -nE '^ENV_|^#?ENV_SAFE' /ManualAI/OmniKnow/omniknow2/server/.env 2>/dev/null | head -20
