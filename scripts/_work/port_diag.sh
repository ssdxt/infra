#!/bin/bash
cd /deploy/code/chat_doc_0918 2>/dev/null || exit 1

echo "########## 1. fschat_controller_address() 完整实现 ##########"
sed -n '460,485p' server/utils.py

echo
echo "########## 2. 各端口的服务身份（看 /docs 标题）##########"
for p in 20400 20401 20402 8261 3333; do
  t=$(curl -sk -m 5 https://127.0.0.1:$p/docs 2>/dev/null | grep -oE "<title>[^<]*</title>" | head -1)
  r=$(curl -sk -m 5 https://127.0.0.1:$p/openapi.json 2>/dev/null | head -c 300)
  echo "--- port $p ---"
  echo "  title: ${t:-<无>}"
  echo "  openapi: ${r:0:200}"
done

echo
echo "########## 3. 占用端口的进程详情 ##########"
for pid in $(ss -tlnp 2>/dev/null | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u); do
  port=$(ss -tlnp 2>/dev/null | grep "pid=$pid," | grep -oE ':[0-9]+ ' | head -3 | tr -d ': ' | tr '\n' ',')
  case "$port" in *2040*|*8261*|*3333*)
    echo "  PID $pid  端口 $port"
    echo "    cmdline: $(tr '\0' ' ' < /proc/$pid/cmdline 2>/dev/null | cut -c1-150)"
    ;;
  esac
done

echo
echo "########## 4. 是否配置了 SSL（controller 用不用 https）##########"
grep -rn "ssl_keyfile\|ssl_certfile\|ssl\b\|https" startup_obd.py 2>/dev/null | head -10
echo "--- server_config.py 里的 SSL/协议配置 ---"
grep -nE "ssl|SSL|https|scheme" configs/server_config.py 2>/dev/null | head -10

echo
echo "########## 5. controller 到底起没起：直接问 20401 要 worker 列表 ##########"
echo "--- POST http://127.0.0.1:20401/refresh_all_workers ---"
curl -s -m 8 -X POST http://127.0.0.1:20401/refresh_all_workers 2>&1 | head -c 200
echo
echo "--- POST https://127.0.0.1:20401/refresh_all_workers ---"
curl -sk -m 8 -X POST https://127.0.0.1:20401/refresh_all_workers 2>&1 | head -c 200
echo
echo "--- GET https://127.0.0.1:20401/list_models ---"
curl -sk -m 8 https://127.0.0.1:20401/list_models 2>&1 | head -c 300
