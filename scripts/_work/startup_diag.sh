#!/bin/bash
cd /deploy/code/chat_doc_0918 2>/dev/null || exit 1
PY=/root/anaconda3/envs/recovery/bin/python

echo "########## 1. startup_obd.py 的参数定义 ##########"
grep -n "add_argument\|args\.\(all_api\|controller\|model_worker\|api\)" startup_obd.py 2>/dev/null | head -30

echo
echo "########## 2. main / 启动分支 ##########"
sed -n '/def main\|__main__/,$p' startup_obd.py 2>/dev/null | head -60

echo
echo "########## 3. FSCHAT_CONTROLLER 配置 ##########"
grep -n -A12 "FSCHAT_CONTROLLER" configs/server_config.py 2>/dev/null | head -25
echo "--- FSCHAT_MODEL_WORKERS（只看端口部分）---"
grep -nE "\"port\"|'port'|FSCHAT_MODEL_WORKERS" configs/server_config.py 2>/dev/null | head -20

echo
echo "########## 4. api_log.txt 里的启动痕迹 ##########"
grep -anE "controller|Controller|worker|Worker|启动|Starting|Running on|Uvicorn" /deploy/cc/logs/api_log.txt 2>/dev/null | head -30

echo
echo "########## 5. api_log.txt 总行数与首尾 ##########"
wc -l /deploy/cc/logs/api_log.txt 2>/dev/null
echo "--- 前 20 行 ---"
head -20 /deploy/cc/logs/api_log.txt 2>/dev/null
