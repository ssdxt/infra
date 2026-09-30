#!/bin/bash
echo '== save_space_image 调用方 =='
grep -rn 'save_space_image' /ManualAI/OmniKnow/omniknow2/server --include='*.py' 2>/dev/null | grep -vE '__pycache__|\.venv' | head -6
echo '== 调用处上下文(ttl 参数) =='
F=$(grep -rln 'save_space_image' /ManualAI/OmniKnow/omniknow2/server --include='*.py' 2>/dev/null | grep -vE '__pycache__|\.venv' | grep -v 'storage/service.py' | head -1)
echo "file: $F"
grep -nB15 -A3 'save_space_image' "$F" 2>/dev/null | head -40
