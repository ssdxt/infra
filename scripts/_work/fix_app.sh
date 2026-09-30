#!/bin/bash
CFG=/deploy/code/chat_doc_0918/configs

echo "=== 1 create chat_doc database ==="
docker exec oceanbase-ce obclient -h127.1 -P2881 -uroot@test -p12345 -e "CREATE DATABASE IF NOT EXISTS chat_doc DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;" 2>&1
docker exec oceanbase-ce obclient -h127.1 -P2881 -uroot@test -p12345 -e "SHOW DATABASES;" 2>&1

echo
echo "=== 2 host pymysql -> 192.168.21.111:2881 ==="
/root/anaconda3/envs/recovery/bin/python -c "import pymysql;c=pymysql.connect(host='192.168.21.111',port=2881,user='root@test',password='12345',database='chat_doc',connect_timeout=8);cur=c.cursor();cur.execute('select database()');print('OK db =',cur.fetchone())" 2>&1 | tail -3

echo
echo "=== 3 backup then replace old IP 192.168.137.33 -> 192.168.21.111 ==="
cd $CFG || exit 1
cp -a kb_config.py kb_config.py.bak-obfix-20260917
cp -a model_config.py model_config.py.bak-obfix-20260917
sed -i 's/192\.168\.137\.33/192.168.21.111/g' kb_config.py model_config.py
echo "--- after ---"
grep -n "192\.168\." kb_config.py model_config.py

echo
echo "=== 4 fix ASCEND_RT_VISIBLE_DEVICES in api_start.sh ==="
cp -a /deploy/cc/bash/api_start.sh /deploy/cc/bash/api_start.sh.bak-obfix-20260917
sed -i 's/ASCEND_RT_VISIBLE_DEVICES=6/ASCEND_RT_VISIBLE_DEVICES=0/' /deploy/cc/bash/api_start.sh
cat /deploy/cc/bash/api_start.sh

echo
echo "=== 5 remove stray tilde from chat_doc_api.service ==="
cp -a /etc/systemd/system/chat_doc_api.service /etc/systemd/system/chat_doc_api.service.bak-obfix-20260917
sed -i '/^~$/d' /etc/systemd/system/chat_doc_api.service
tail -5 /etc/systemd/system/chat_doc_api.service
systemctl daemon-reload
echo "daemon-reloaded"

echo
echo "=== 6 what does init_database.py do ==="
head -45 /deploy/code/chat_doc_0918/init_database.py 2>&1

echo
echo "=== 7 restart api + web ==="
systemctl restart chat_doc_api
sleep 5
systemctl restart chat_doc_web
sleep 75
systemctl status chat_doc_api --no-pager -l 2>&1 | head -12
echo
systemctl status chat_doc_web --no-pager -l 2>&1 | head -10

echo
echo "=== 8 app log tail ==="
tail -35 /deploy/cc/logs/api_log.txt 2>&1

echo
echo "=== 9 probes ==="
curl -sk -m 10 -o /dev/null -w "  api /docs    HTTP %{http_code}\n" https://127.0.0.1:8261/docs
curl -sk -m 10 -o /dev/null -w "  web https /  HTTP %{http_code}\n" https://127.0.0.1:3333/
curl -sk -m 15 -o /tmp/openapi.json https://127.0.0.1:8261/openapi.json 2>&1
echo "  routes:"
grep -o '"/[a-zA-Z0-9_/-]*"' /tmp/openapi.json 2>/dev/null | sort -u | head -50

echo
echo "=== 10 ports ==="
ss -lntp 2>/dev/null | grep -E ':(8261|20400|20401|3333|2881)'
