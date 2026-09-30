#!/bin/bash
echo "########## 1. api_start.sh 当前内容 ##########"
cat -A /deploy/cc/bash/api_start.sh 2>&1 | sed 's/\$$//'

echo
echo "########## 2. 完整失败日志（journalctl）##########"
journalctl -u chat_doc_api -b --no-pager -o cat 2>/dev/null | tail -60

echo
echo "########## 3. api_log.txt ##########"
ls -la /deploy/cc/logs/ 2>&1
echo "--- 内容 ---"
tail -60 /deploy/cc/logs/api_log.txt 2>&1

echo
echo "########## 4. 复现：直接在命令行跑一遍 ##########"
source /root/anaconda3/bin/activate recovery 2>/dev/null
cd /deploy/code/chat_doc_0918 2>/dev/null || echo "目录不存在"
python -c "import fastapi; print('fastapi', fastapi.__version__)" 2>&1 | tail -20

echo
echo "########## 5. 关键包版本 ##########"
python -c "
import importlib.metadata as m
for p in ['fastapi','pydantic','pydantic-core','starlette','uvicorn','typing-extensions','anyio']:
    try: print(f'  {p:20} {m.version(p)}')
    except Exception as e: print(f'  {p:20} <缺失>')
" 2>&1

echo
echo "########## 6. python 版本 ##########"
python -V 2>&1
which python
