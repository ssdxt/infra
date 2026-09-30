#!/bin/bash
cd /deploy/code/chat_doc_0918 2>/dev/null || exit 1

echo "########## 问题1: /openapi.json 的 file_parse_configs 定义 ##########"
grep -rn "file_parse_configs" --include="*.py" . 2>/dev/null | head -10

echo
echo "--- update_configs_to_db 接口定义 ---"
grep -rn -B3 -A18 "def update_configs_to_db" --include="*.py" . 2>/dev/null | head -40

echo
echo "########## 问题2: web 服务 ##########"
echo "--- /deploy/code/web_0918 目录 ---"
ls -la /deploy/code/web_0918/ 2>&1 | head -20
echo
echo "--- https_server.py 内容 ---"
cat /deploy/code/web_0918/https_server.py 2>&1 | head -50

echo
echo "--- 进程 1784 在等什么 ---"
cat /proc/1784/wchan 2>/dev/null; echo
echo "--- 进程状态 ---"
cat /proc/1784/status 2>/dev/null | grep -E "State|Threads|VmRSS"
echo "--- 打开的 fd ---"
ls -l /proc/1784/fd 2>/dev/null | head -15

echo
echo "--- 进程树 ---"
ps -ef | grep -E "1784|1427|https_server" | grep -v grep
