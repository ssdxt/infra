#!/bin/bash
echo '== 找 images/upload 实际路由 =='
grep -rn 'images/upload' /ManualAI/OmniKnow/omniknow2/server/api/endpoints/*.py 2>/dev/null | head -5
echo '== 路由实现 =='
grep -rnB2 -A18 'images/upload' /ManualAI/OmniKnow/omniknow2/server/api/endpoints/space.py 2>/dev/null | head -40
echo '== ttl / expire 相关配置 =='
grep -rniE 'ttl|expire|presign|signed' /ManualAI/OmniKnow/omniknow2/server/api/endpoints/space.py /ManualAI/OmniKnow/omniknow2/server/core/config.py 2>/dev/null | grep -vE '__pycache__|\.venv' | head -15
