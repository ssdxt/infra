#!/bin/bash
echo '== 登录路由 ='
grep -rnE 'auth/login|def login|class .*Login' /ManualAI/OmniKnow/omniknow2/server/api/*.py /ManualAI/OmniKnow/omniknow2/server/api/**/*.py 2>/dev/null | head -8
echo '== 登录请求模型字段 ='
grep -rnB2 -A12 'class Login' /ManualAI/OmniKnow/omniknow2/server/api/*.py /ManualAI/OmniKnow/omniknow2/server/api/**/*.py /ManualAI/OmniKnow/omniknow2/server/schemas/*.py /ManualAI/OmniKnow/omniknow2/server/entities/*.py 2>/dev/null | head -25
echo '== 图片上传路由 ='
grep -rnE 'images/upload|def upload.*image|save_space_image' /ManualAI/OmniKnow/omniknow2/server/api/*.py /ManualAI/OmniKnow/omniknow2/server/api/**/*.py 2>/dev/null | head -6
