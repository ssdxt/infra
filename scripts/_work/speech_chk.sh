#!/bin/bash
echo "=== 1 speech service detail ==="
systemctl status chat_doc_speech --no-pager -l 2>&1 | head -22

echo
echo "=== 2 speech processes ==="
ps -ef | grep -iE "web_demo_seaco|melo" | grep -v grep | head -5

echo
echo "=== 3 speech stderr tail ==="
tail -25 /var/log/chat_doc_speech.err 2>&1
echo "--- stdout tail ---"
tail -12 /var/log/chat_doc_speech.log 2>&1

echo
echo "=== 4 what has been extracted so far ==="
ls -la /deploy/models/speech/ 2>&1
echo "--- speech/iic ---"
ls -la /deploy/models/speech/iic/ 2>&1

echo
echo "=== 5 models needed by web_demo_seaco.py ==="
grep -n "model_path\s*=" /deploy/code/melott/web_demo_seaco.py 2>&1 | head -5
echo "--- melo refs ---"
grep -n "/deploy/models\|melo" /deploy/code/melott/web_demo_seaco.py 2>&1 | head -15

echo
echo "=== 6 extraction progress ==="
du -sh /deploy/models/speech 2>&1
ps -ef | grep unrar | grep -v grep | head -2
tail -c 200 /tmp/unrar_speech.log 2>&1

echo
echo "=== 7 port 7870 ==="
ss -lntp 2>/dev/null | grep 7870 || echo "  7870 未监听"
