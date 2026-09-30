#!/bin/bash
echo '== static pem 文件 =='
ls -la /ManualAI/OmniKnow/omniknow2/server/static/*.pem 2>/dev/null || find /ManualAI/OmniKnow/omniknow2/server -maxdepth 2 -name '*.pem' 2>/dev/null
echo '== utils/crypto.py =='
cat /ManualAI/OmniKnow/omniknow2/server/utils/crypto.py 2>/dev/null | head -40
echo '== services/auth.py 30-70 行 =='
sed -n '30,70p' /ManualAI/OmniKnow/omniknow2/server/services/auth.py 2>/dev/null
