#!/bin/bash
echo "########## 1. /openapi.json 500 的原因（8261）##########"
START=$(systemctl show chat_doc_api -p ActiveEnterTimestamp --value)
journalctl -u chat_doc_api --since "$START" --no-pager -o cat 2>/dev/null \
  | grep -A25 "openapi\|OpenAPI" | tail -35

echo
echo "########## 2. 8261 各接口状态 ##########"
for ep in / /docs /openapi.json /health /v1/models; do
  printf "  %-16s " "$ep"
  curl -s -o /dev/null -w "HTTP %{http_code}\n" -m 8 http://127.0.0.1:8261$ep 2>/dev/null
done
echo "--- / 返回内容 ---"
curl -s -m 8 http://127.0.0.1:8261/ | head -c 300
echo

echo
echo "########## 3. web 服务 (3333) 诊断 ##########"
echo "--- 进程 ---"
ps -o pid,ppid,user,stat,etime,cmd -p 1784 2>/dev/null
echo "--- 端口详情 ---"
ss -tlnp 2>/dev/null | grep 3333
echo "--- 详细握手 ---"
curl -v -m 6 http://127.0.0.1:3333/ 2>&1 | grep -E "^[<>*]|Connected|refused|reset|HTTP" | head -15
echo
echo "--- https 握手 ---"
curl -vk -m 6 https://127.0.0.1:3333/ 2>&1 | grep -E "^[<>*]|Connected|refused|reset|HTTP|SSL|error" | head -15

echo
echo "########## 4. web 服务的 systemd 定义与日志 ##########"
systemctl cat chat_doc_web 2>/dev/null | grep -vE "^\s*#|^\s*$"
echo "--- 最近日志 ---"
journalctl -u chat_doc_web -n 20 --no-pager -o cat 2>/dev/null | tail -20

echo
echo "########## 5. web_start.sh 内容 ##########"
cat /deploy/cc/bash/web_start.sh 2>/dev/null
echo "--- web 目录 ---"
grep -oE '/deploy/[a-zA-Z0-9_/.-]+' /deploy/cc/bash/web_start.sh 2>/dev/null | head -3
