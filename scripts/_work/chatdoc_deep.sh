#!/bin/bash
echo "########## A 语音服务的真实错误日志 ##########"
echo "===== /var/log/chat_doc_speech.err (tail 80) ====="
tail -80 /var/log/chat_doc_speech.err 2>&1
echo
echo "===== /var/log/chat_doc_speech.log (tail 40) ====="
tail -40 /var/log/chat_doc_speech.log 2>&1

echo
echo "########## B OceanBase 容器内部到底怎么了 ##########"
echo "===== /root/boot/start.sh ====="
docker exec oceanbase-ce cat /root/boot/start.sh 2>&1
echo
echo "===== 容器内目录 ====="
docker exec oceanbase-ce ls -la /root/ 2>&1
echo "--- /root/ob ---"
docker exec oceanbase-ce ls -la /root/ob 2>&1 | head -20
echo "--- /root/obd ---"
docker exec oceanbase-ce ls -la /root/obd 2>&1 | head -20
echo "--- 找 observer.log ---"
docker exec oceanbase-ce find /root -maxdepth 4 -name "observer.log*" 2>/dev/null | head -5
echo "--- 找 observer 进程/二进制 ---"
docker exec oceanbase-ce find /root -maxdepth 4 -name "observer" -type f 2>/dev/null | head -5

echo
echo "########## C observer 日志尾部 ##########"
docker exec oceanbase-ce sh -c 'L=$(ls -t /root/ob/log/observer.log* 2>/dev/null | head -1); echo "latest=$L"; tail -60 "$L" 2>/dev/null' 2>&1

echo
echo "########## D 容器本身的 docker 日志 ##########"
docker logs --tail 50 oceanbase-ce 2>&1
echo "--- 容器状态 ---"
docker inspect -f '  State={{.State.Status}} ExitCode={{.State.ExitCode}} Restarts={{.RestartCount}} Started={{.State.StartedAt}}' oceanbase-ce 2>&1

echo
echo "########## E 应用数据库配置定位 ##########"
echo "--- /deploy/code/chat_doc_0918 顶层 ---"
ls -la /deploy/code/chat_doc_0918/ 2>&1 | head -30
echo "--- 搜 2881 ---"
grep -rn "2881" /deploy/code/chat_doc_0918 2>/dev/null | head -15
echo "--- 搜 oceanbase ---"
grep -rni "oceanbase" /deploy/code/chat_doc_0918 2>/dev/null | head -15
echo "--- 搜 chat_doc 库名 ---"
grep -rn "chat_doc" /deploy/code/chat_doc_0918 2>/dev/null | grep -iE "database|db_|host|port|user|pass" | head -15

echo
echo "########## F GLM-4 现在通不通 ##########"
curl -s -m 8 -o /tmp/m.json -w "  /v1/models HTTP %{http_code}\n" http://127.0.0.1:10006/v1/models 2>&1
head -c 300 /tmp/m.json 2>/dev/null; echo
echo "  --- 实测对话 ---"
curl -s -m 90 -X POST http://127.0.0.1:10006/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"glm-4","messages":[{"role":"user","content":"你好"}],"max_tokens":16}' -w '\n  HTTP %{http_code}\n' 2>&1 | head -c 700

echo
echo "########## G 三个服务端口复核 ##########"
ss -lntp 2>/dev/null | grep -E ':(8261|20400|20401|3333|7870|10006|2881|8105|8106)'
