#!/bin/bash
echo "########## 1. controller 通信（HTTP 直连）##########"
echo -n "  POST http://127.0.0.1:20401/list_models        -> "
curl -s -m 8 -X POST http://127.0.0.1:20401/list_models | head -c 200
echo
echo -n "  POST http://127.0.0.1:20401/refresh_all_workers -> "
curl -s -m 8 -X POST http://127.0.0.1:20401/refresh_all_workers | head -c 200
echo
echo -n "  POST http://127.0.0.1:20401/worker_get_status  -> "
curl -s -m 8 -X POST http://127.0.0.1:20401/worker_get_status | head -c 200
echo

echo
echo "########## 2. OpenAI 兼容接口 ##########"
for ep in /v1/models /docs /openapi.json; do
  printf "  %-18s " "$ep"
  curl -s -o /dev/null -w "HTTP %{http_code}\n" -m 10 http://127.0.0.1:20400$ep
done
echo "--- /v1/models 内容 ---"
curl -s -m 10 http://127.0.0.1:20400/v1/models | head -c 500
echo

echo
echo "########## 3. Chat_Doc API 接口 ##########"
for ep in /docs /openapi.json; do
  printf "  %-18s " "$ep"
  curl -s -o /dev/null -w "HTTP %{http_code}\n" -m 10 http://127.0.0.1:8261$ep
done

echo
echo "########## 4. web 服务 ##########"
printf "  https://127.0.0.1:3333/  "
curl -sk -o /dev/null -w "HTTP %{http_code}\n" -m 8 https://127.0.0.1:3333/
printf "  http://127.0.0.1:3333/   "
curl -s -o /dev/null -w "HTTP %{http_code}\n" -m 8 http://127.0.0.1:3333/

echo
echo "########## 5. 重启后的日志：还有没有 ServerDisconnectedError ##########"
START=$(systemctl show chat_doc_api -p ActiveEnterTimestamp --value)
echo "  服务启动于: $START"
journalctl -u chat_doc_api --since "$START" --no-pager -o cat 2>/dev/null \
  | grep -icE "ServerDisconnectedError|Exception in ASGI" | sed 's/^/  相关错误行数: /'
echo "--- 若上面是 0，说明协议问题已解决 ---"

echo
echo "########## 6. 主动触发一次 /v1/models 后再看日志 ##########"
curl -s -o /dev/null -m 10 http://127.0.0.1:20400/v1/models
sleep 3
journalctl -u chat_doc_api --since "$START" --no-pager -o cat 2>/dev/null \
  | grep -cE "ServerDisconnectedError" | sed 's/^/  触发后累计 ServerDisconnectedError: /'

echo
echo "########## 7. 服务状态汇总 ##########"
for s in chat_doc_api chat_doc_web chat_doc_speech; do
  printf "  %-20s %s\n" "$s" "$(systemctl is-active $s)"
done
echo
echo "--- 监听端口 ---"
ss -tlnp 2>/dev/null | grep -E ":(20400|20401|20402|8261|3333|7870) " | awk '{print "  "$4"  "$6}'
