#!/bin/bash
set -u
PKG=/root/anaconda3/envs/recovery/lib/python3.8/site-packages
PY=/root/anaconda3/envs/recovery/bin/python
BK=/deploy/cc/logs/pkg-backup-$(date +%Y%m%d-%H%M%S)

echo "########## 1. 备份将被移除的文件 ##########"
mkdir -p "$BK"
cp -a $PKG/fastapi/_compat                  "$BK"/ 2>/dev/null && echo "  备份 _compat/"
cp -a $PKG/fastapi-0.124.4.dist-info        "$BK"/ 2>/dev/null && echo "  备份 fastapi-0.124.4.dist-info"
cp -a $PKG/fastapi/temp_pydantic_v1_params.py "$BK"/ 2>/dev/null && echo "  备份 temp_pydantic_v1_params.py"
ls -la "$BK"
echo "备份目录: $BK"

echo
echo "########## 2. 移除 0.124.4 残留 ##########"
rm -rf $PKG/fastapi/_compat
rm -f  $PKG/fastapi/temp_pydantic_v1_params.py
rm -rf $PKG/fastapi-0.124.4.dist-info
find $PKG/fastapi -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
echo "  已移除"
echo "--- 剩余 dist-info ---"
ls -d $PKG/fastapi-*.dist-info 2>&1
echo "--- fastapi/_compat.* 现状 ---"
ls -ld $PKG/fastapi/_compat.py $PKG/fastapi/_compat 2>&1

echo
echo "########## 3. 验证导入 ##########"
$PY - <<'EOF'
import fastapi
print("  fastapi __version__ :", fastapi.__version__)
from fastapi import FastAPI
print("  from fastapi import FastAPI          【OK】")
from fastapi._compat import ErrorWrapper
print("  from fastapi._compat import ErrorWrapper  【OK】")
import importlib.metadata as m
print("  importlib.metadata  :", m.version("fastapi"))
EOF

echo
echo "########## 4. 验证应用模块能导入 ##########"
cd /deploy/code/chat_doc_0918 || exit 1
timeout 120 $PY -c "
import sys
sys.argv=['x']
from server.utils import get_httpx_client
print('  server.utils 导入 【OK】')
" 2>&1 | tail -15

echo
echo "########## 5. 重启服务 ##########"
systemctl restart chat_doc_api 2>&1
sleep 25
systemctl status chat_doc_api --no-pager 2>&1 | head -18

echo
echo "########## 6. 端口监听 ##########"
ss -tlnp 2>/dev/null | grep -E "8261|20400|20401|3333|7870" || echo "  (未监听)"
