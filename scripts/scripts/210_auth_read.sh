#!/bin/bash
echo '== auth.py login 相关 ====='
grep -nB3 -A30 'def login' /ManualAI/OmniKnow/omniknow2/server/api/endpoints/auth.py 2>/dev/null | head -50
echo '== RSA 文件 ====='
find /ManualAI/OmniKnow/omniknow2/server -name '*rsa*' -o -name '*\.pem' 2>/dev/null | grep -v __pycache__ | head
