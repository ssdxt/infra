#!/bin/bash
echo "########## 1. 各端口的协议与响应 ##########"
for p in 8261 20400 20401 3333; do
  printf "  port %-6s " $p
  code=$(curl -sk -o /dev/null -w "%{http_code}" -m 8 https://127.0.0.1:$p/ 2>/dev/null)
  echo -n "https=$code "
  code2=$(curl -s -o /dev/null -w "%{http_code}" -m 8 http://127.0.0.1:$p/ 2>/dev/null)
  echo "http=$code2"
done

echo
echo "########## 2. uvicorn 实际监听（从应用日志看）##########"
grep -aE "Uvicorn running on|Started server process" /deploy/cc/logs/api_log.txt 2>/dev/null | tail -10

echo
echo "########## 3. /docs 与 /v1/models（https + 忽略证书）##########"
echo "--- https://127.0.0.1:20400/docs ---"
curl -sk -o /dev/null -w "  HTTP %{http_code}\n" -m 10 https://127.0.0.1:20400/docs
echo "--- https://127.0.0.1:20400/v1/models ---"
curl -sk -m 10 https://127.0.0.1:20400/v1/models 2>&1 | head -c 400
echo
echo "--- https://127.0.0.1:20401/docs ---"
curl -sk -o /dev/null -w "  HTTP %{http_code}\n" -m 10 https://127.0.0.1:20401/docs

echo
echo "########## 4. 只看【本次启动之后】的日志 ##########"
START=$(systemctl show chat_doc_api -p ActiveEnterTimestamp --value 2>/dev/null)
echo "  服务启动于: $START"
journalctl -u chat_doc_api --since "$START" --no-pager -o cat 2>/dev/null \
  | grep -iE "error|traceback|exception|failed|critical" \
  | grep -viE "Please use PaddlePaddle with GPU|Ultralytics|Settings reset|pytree_node|INFO" \
  | tail -12
echo "  (以上为空=启动后无实质错误)"

echo
echo "########## 5. 本次启动日志尾部 ##########"
journalctl -u chat_doc_api --since "$START" --no-pager -o cat 2>/dev/null | tail -12

echo
echo "########## 6. 三个服务状态 ##########"
for s in chat_doc_api chat_doc_web chat_doc_speech; do
  printf "  %-20s %-10s %s\n" "$s" "$(systemctl is-active $s)" "$(systemctl show $s -p ActiveEnterTimestamp --value)"
done
