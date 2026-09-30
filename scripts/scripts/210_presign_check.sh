#!/bin/bash
echo '== OssSettings 配置定义 =='
grep -nB2 -A18 'class OssSettings' /ManualAI/OmniKnow/omniknow2/server/core/config.py 2>/dev/null | head -30
echo '== presign 实现（endpoint 怎么拼） =='
grep -rnB3 -A15 'async def presign' /ManualAI/OmniKnow/omniknow2/server/storage/backends/s3.py 2>/dev/null | head -30
echo '== wan/endpoint 构造处 =='
grep -rnE 'wan|presign|endpoint_url|oss_ssl|OSS_SSL' /ManualAI/OmniKnow/omniknow2/server/storage/service.py /ManualAI/OmniKnow/omniknow2/server/storage/__init__.py /ManualAI/OmniKnow/omniknow2/server/core/config.py 2>/dev/null | grep -vE '__pycache__|\.venv' | head -15
