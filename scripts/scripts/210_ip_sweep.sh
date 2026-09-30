#!/bin/bash
echo '===== 1. omniknow2 代码/配置里的残留 IP ====='
grep -rnE '192\.168\.0\.23|192\.168\.5\.60|192\.168\.50\.71|115\.120\.240\.126|183\.129\.232\.94' /ManualAI/OmniKnow/omniknow2 --include='*.py' --include='*.env*' --include='*.yaml' --include='*.yml' --include='*.conf' --include='*.json' 2>/dev/null | grep -vE '__pycache__|\.venv|\.bak' | head -25
echo
echo '===== 2. 前端静态(html/omniknow)里的 IP / 后端地址 ====='
ls /ManualAI/OmniKnow/data/nginx/html/omniknow/ 2>/dev/null | head -10
echo '--- config.json ---'
cat /ManualAI/OmniKnow/data/nginx/html/omniknow/config.json 2>/dev/null
echo '--- js 里搜 IP/8375 ---'
grep -rloE '192\.168\.0\.23|115\.120\.240\.126|192\.168\.5\.60|:8375' /ManualAI/OmniKnow/data/nginx/html/omniknow/ 2>/dev/null | head -5
echo
echo '===== 3. list_resource_service.py 内容 ====='
grep -nE '192\.168|http|8375|8366|URL' /ManualAI/OmniKnow/omniknow2/assistant/scripts/rag/list_resource_service.py 2>/dev/null | head -12
