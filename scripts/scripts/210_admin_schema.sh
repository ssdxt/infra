#!/bin/bash
echo '== admin/schema.py 里创建用户模型 =='
grep -nB2 -A22 'class .*User.*Create\|password' /ManualAI/OmniKnow/omniknow2/server/admin/schema.py 2>/dev/null | head -50
echo '== admin/api.py 创建用户路由 =='
grep -nB3 -A20 "def create\|/users\"" /ManualAI/OmniKnow/omniknow2/server/admin/api.py 2>/dev/null | grep -vE '^\s*#' | head -35
