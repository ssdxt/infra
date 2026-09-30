#!/bin/bash
PY=/root/anaconda3/envs/recovery/bin/python

echo "########## 1. 清掉过期的 __pycache__ ##########"
find /root/anaconda3/envs/recovery/lib/python3.8/site-packages -name "__pycache__" -type d -newermt "2026-09-01" 2>/dev/null | head -3
find /deploy/code/chat_doc_0918 -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
echo "  已清理"

echo
echo "########## 2. 应用模块导入测试 ##########"
cd /deploy/code/chat_doc_0918 || exit 1
timeout 300 $PY -c "
import sys; sys.argv=['x']
from server.utils import get_httpx_client
print('  server.utils           【OK】')
import fastapi, transformers, tokenizers, torch, starlette, pydantic
print('  fastapi     ', fastapi.__version__)
print('  transformers', transformers.__version__)
print('  tokenizers  ', tokenizers.__version__)
print('  torch       ', torch.__version__)
print('  starlette   ', starlette.__version__)
print('  pydantic    ', pydantic.VERSION)
" 2>&1 | tail -25

echo
echo "########## 3. 重启 chat_doc_api ##########"
systemctl restart chat_doc_api
sleep 40
systemctl status chat_doc_api --no-pager 2>&1 | head -16

echo
echo "########## 4. 端口监听 ##########"
ss -tlnp 2>/dev/null | grep -E "8261|20400|20401|3333|7870" || echo "  (未监听)"

echo
echo "########## 5. api_log.txt 尾部 ##########"
tail -30 /deploy/cc/logs/api_log.txt 2>&1
