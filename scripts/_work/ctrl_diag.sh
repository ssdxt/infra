#!/bin/bash
cd /deploy/code/chat_doc_0918 2>/dev/null || exit 1
PY=/root/anaconda3/envs/recovery/bin/python

echo "########## 1. controller_address 的来源 ##########"
grep -rn "fschat_controller_address\|FSCHAT_CONTROLLER\|controller_address" server/utils.py 2>/dev/null | head -10
echo "--- model_config.py 里的 controller 定义 ---"
grep -rn "FSCHAT_CONTROLLER\|CONTROLLER_ADDRESS\|controller" configs/model_config.py 2>/dev/null | head -15

echo
echo "########## 2. 启动参数 --all-api 做了什么 ##########"
grep -n "all-api\|all_api\|controller\|worker" startup_obd.py 2>/dev/null | head -25

echo
echo "########## 3. 相关端口现状 ##########"
echo "--- 所有监听端口 ---"
ss -tlnp 2>/dev/null | awk 'NR==1 || /LISTEN/' | head -25

echo
echo "########## 4. controller / worker 端口探测 ##########"
for p in 20001 20002 21001 21002 21003 21004 21005 21006 21007 21008; do
  if ss -tln 2>/dev/null | grep -q ":$p "; then
    echo "  端口 $p  已监听  -> $(ss -tlnp 2>/dev/null | grep ":$p " | grep -oE 'users:\(\([^)]*\)\)' | head -1)"
  fi
done
echo "  (以上未列出的端口均未监听)"

echo
echo "########## 5. 日志里应用自己报的端口 ##########"
grep -aE "Uvicorn running|Running on|http://|https://" /deploy/cc/logs/api_log.txt 2>/dev/null \
  | grep -aiE "running|started" | tail -12

echo
echo "########## 6. 直接复现 ##########"
echo "--- GET /v1/models ---"
curl -sk -m 10 https://127.0.0.1:20400/v1/models 2>&1 | head -c 200
echo
echo "--- 试试 controller 本身 ---"
CTRL=$(grep -rhoE "FSCHAT_CONTROLLER[^}]*" configs/model_config.py 2>/dev/null | head -3)
echo "  配置片段: $CTRL"
for p in 20001 21001; do
  printf "  127.0.0.1:%-6s -> " $p
  curl -s -o /dev/null -w "http=%{http_code} " -m 3 http://127.0.0.1:$p/ 2>/dev/null
  echo
done
