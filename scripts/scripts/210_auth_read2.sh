#!/bin/bash
echo '== auth.py 里 login 相关行 =='
grep -n 'login' /ManualAI/OmniKnow/omniknow2/server/api/endpoints/auth.py 2>/dev/null | head -10
echo '== 登录函数上下文 ====='
grep -nB2 -A25 'router.post("/login"' /ManualAI/OmniKnow/omniknow2/server/api/endpoints/auth.py 2>/dev/null | head -45
echo '== rsa / ENV_RSA 引用 ====='
grep -rnE 'rsa_private|ENV_RSA|rsa\.|RSA' /ManualAI/OmniKnow/omniknow2/server --include='*.py' 2>/dev/null | grep -vE '__pycache__|\.venv' | head -12
echo '== 密码校验函数 ====='
grep -rnE 'def .*password|check_password|verify|salt' /ManualAI/OmniKnow/omniknow2/server/core/security.py /ManualAI/OmniKnow/omniknow2/server/db/*.py /ManualAI/OmniKnow/omniknow2/server/services/*.py 2>/dev/null | grep -vE '__pycache__|\.venv' | head -12
