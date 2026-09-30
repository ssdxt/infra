#!/bin/bash
PKG=/root/anaconda3/envs/recovery/lib/python3.8/site-packages
PY=/root/anaconda3/envs/recovery/bin/python
BK=/deploy/cc/logs/pkg-backup-20260914-093505

echo "########## 1. 备份并移除 charset_normalizer 3.5.1 残留 ##########"
cp -a $PKG/charset_normalizer/cd.abi3.so $BK/ 2>/dev/null
cp -a $PKG/charset_normalizer/md.abi3.so $BK/ 2>/dev/null
cp -a $PKG/charset_normalizer-3.5.1.dist-info $BK/ 2>/dev/null
rm -f  $PKG/charset_normalizer/cd.abi3.so
rm -f  $PKG/charset_normalizer/md.abi3.so
rm -rf $PKG/charset_normalizer-3.5.1.dist-info
find $PKG/charset_normalizer -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
echo "  已移除，备份在 $BK"

echo
echo "########## 2. 验证 ##########"
$PY -c "
import charset_normalizer as c
print('  charset_normalizer:', c.__version__)
from charset_normalizer import from_bytes
print('  from_bytes OK ->', from_bytes('你好 hello'.encode()).best())
import requests
print('  requests:', requests.__version__, '【OK】')
"

echo
echo "########## 3. 应用模块导入测试 ##########"
cd /deploy/code/chat_doc_0918 || exit 1
timeout 180 $PY -c "
import sys; sys.argv=['x']
from server.utils import get_httpx_client
print('  server.utils 【OK】')
" 2>&1 | tail -20

echo
echo "########## 4. 重启 chat_doc_api ##########"
systemctl restart chat_doc_api
sleep 30
systemctl status chat_doc_api --no-pager 2>&1 | head -14

echo
echo "########## 5. 端口 ##########"
ss -tlnp 2>/dev/null | grep -E "8261|20400|20401" || echo "  (API 端口未监听)"

echo
echo "########## 6. api_log.txt ##########"
tail -25 /deploy/cc/logs/api_log.txt 2>&1
