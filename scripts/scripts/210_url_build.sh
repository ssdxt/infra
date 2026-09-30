#!/bin/bash
echo '== URL 构造相关 ====='
grep -nB2 -A20 'def _signed_url_dict\|def public_url\|def _signed_url' /ManualAI/OmniKnow/omniknow2/server/storage/service.py 2>/dev/null | head -60
echo '== OSS_WAN 配置引用 ====='
grep -rnE 'OSS_WAN|oss_wan|WAN_HOST|WAN_PORT' /ManualAI/OmniKnow/omniknow2/server --include='*.py' 2>/dev/null | grep -vE '__pycache__|\.venv' | head -10
echo '== config.py OSS 字段 ====='
grep -nB2 -A6 'OSS_WAN\|oss_wan\|oss:' /ManualAI/OmniKnow/omniknow2/server/core/config.py 2>/dev/null | head -30
