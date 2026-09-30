#!/bin/bash
echo '===== s3.py split_namespace / public 映射 ====='
sed -n '1,60p' /ManualAI/OmniKnow/omniknow2/server/storage/backends/s3.py 2>/dev/null
echo
echo '===== save_space_image 调用段 ====='
sed -n '120,160p' /ManualAI/OmniKnow/omniknow2/server/storage/service.py 2>/dev/null
echo
echo '===== rag/.env 全文 ====='
cat /ManualAI/OmniKnow/omniknow2/parser/rag/.env 2>/dev/null
echo
echo '===== GPU 当前占用 ====='
nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv,noheader 2>/dev/null
