#!/bin/bash
echo '== aiserver.log 里 admin/users 最近记录 =='
grep -aE 'admin/users' /ManualAI/OmniKnow/logs/aiserver.log 2>/dev/null | tail -8
echo
echo '== admin/users 路由定义 =='
grep -rn 'admin/users' /ManualAI/OmniKnow/omniknow2/server/api/endpoints/*.py 2>/dev/null | grep -v '#' | head -5
F=$(grep -rln 'admin/users' /ManualAI/OmniKnow/omniknow2/server/api/endpoints/*.py 2>/dev/null | grep -v '#' | head -1)
echo "file: $F"
grep -nB3 -A20 "admin/users" "$F" 2>/dev/null | head -40
