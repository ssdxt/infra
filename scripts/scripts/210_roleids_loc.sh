#!/bin/bash
echo '== role_ids 出现文件 =='
grep -rln 'role_ids' /ManualAI/OmniKnow/omniknow2/server --include='*.py' 2>/dev/null | grep -vE '__pycache__|\.venv' | head -8
echo '== admin/users 路由文件 =='
grep -rln 'admin/users' /ManualAI/OmniKnow/omniknow2/server --include='*.py' 2>/dev/null | grep -vE '__pycache__|\.venv' | head -5
echo '== 创建用户 body 模型字段(password 定义) =='
F=$(grep -rln 'role_ids' /ManualAI/OmniKnow/omniknow2/server --include='*.py' 2>/dev/null | grep -vE '__pycache__|\.venv' | grep -iE 'endpoint|service' | head -1)
echo "file: $F"
grep -nB10 'role_ids' "$F" 2>/dev/null | head -40
