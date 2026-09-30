#!/bin/bash
echo '== 192.168.0.23 出现位置(parser) =='
grep -rn '192\.168\.0\.23' /ManualAI/OmniKnow/omniknow2/parser/rag --include='*.py' 2>/dev/null | grep -vE '__pycache__' | head -10
echo '== 18080 / img 服务地址相关配置 =='
grep -rnE '18080|IMG_SERVER|img_server|IMG_URL|image_url' /ManualAI/OmniKnow/omniknow2/parser/rag --include='*.py' 2>/dev/null | grep -vE '__pycache__' | grep -iE 'http|url|getenv|environ|=' | head -12
