#!/bin/bash
echo '===== aiserver 最近 docs/upload 相关 ====='
grep -E 'docs/upload|docs/parse|resources' /ManualAI/OmniKnow/logs/aiserver.log 2>/dev/null | tail -12
echo
echo '===== nginx access 最近 15 条 ====='
ls -t /ManualAI/OmniKnow/data/nginx/logs/access_*.log 2>/dev/null | head -1 | xargs tail -15 2>/dev/null
echo
echo '===== docs/upload 路由定义 ====='
grep -rn 'docs/upload' /ManualAI/OmniKnow/omniknow2/server/api/endpoints/*.py 2>/dev/null | grep -v '#' | head -5
F=$(grep -rln 'docs/upload' /ManualAI/OmniKnow/omniknow2/server/api/endpoints/*.py 2>/dev/null | grep -v '#' | head -1)
echo "route file: $F"
grep -nB5 -A25 'docs/upload' "$F" 2>/dev/null | head -45
