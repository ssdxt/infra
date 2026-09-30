#!/bin/bash
echo '== S3Backend / presign 装配处 =='
grep -rnB3 -A15 'S3Backend(\|presign_backend=\|PrestoBackend\|wan' /ManualAI/OmniKnow/omniknow2/server/core/startup.py /ManualAI/OmniKnow/omniknow2/server/db/*.py /ManualAI/OmniKnow/omniknow2/server/main.py 2>/dev/null | grep -vE '__pycache__|\.venv' | head -30
echo '== 找所有 S3Backend 实例化 =='
grep -rn 'S3Backend(' /ManualAI/OmniKnow/omniknow2/server --include='*.py' 2>/dev/null | grep -vE '__pycache__|\.venv' | head -8
