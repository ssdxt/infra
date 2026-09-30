#!/bin/bash
echo "=== 1 extraction progress ==="
cat /tmp/extract_models.log 2>&1 | tail -6
echo "--- unrar processes ---"
ps -ef | grep unrar | grep -v grep | head -3
echo "--- speed check: speech dir size ---"
du -sh /deploy/models/speech 2>&1
du -sh /deploy/models/melo 2>&1
echo "--- free space ---"
df -h / | tail -1

echo
echo "=== 2 speech.rar log ==="
tail -3 /tmp/unrar_speech.log 2>&1

echo
echo "=== 3 find FastAPI app definition ==="
ls -la /deploy/code/chat_doc_0918/server/http_api/ 2>&1
echo "--- @app / @router decorators ---"
grep -rn "@app\.\|@router\." /deploy/code/chat_doc_0918/server/ 2>/dev/null | head -30
echo "--- FastAPI( / APIRouter( ---"
grep -rn "FastAPI(\|APIRouter(" /deploy/code/chat_doc_0918/ --include=*.py 2>/dev/null | head -20

echo
echo "=== 4 startup_obd.py 里的路由挂载 ==="
grep -n "include_router\|mount\|add_api_route\|app\.\|url_path" /deploy/code/chat_doc_0918/startup_obd.py 2>/dev/null | head -30

echo
echo "=== 5 service state ==="
systemctl is-active chat_doc_api chat_doc_web chat_doc_speech 2>&1
ss -lntp 2>/dev/null | grep -E ':(8261|3333|7870|2881|10006|8105|8106)'
