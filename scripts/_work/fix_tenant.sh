#!/bin/bash
CFG=/deploy/code/chat_doc_0918/configs

echo "=== 1 fix DB URI: add tenant -> root%40test ==="
cd $CFG || exit 1
sed -i 's|mysql+pymysql://root:12345@192.168.21.111:2881/chat_doc|mysql+pymysql://root%40test:12345@192.168.21.111:2881/chat_doc|' kb_config.py
grep -n "SQLALCHEMY_DATABASE_URI" kb_config.py

echo
echo "=== 2 fix remaining stale IPs ==="
cp -a /deploy/code/chat_doc_0918/server/chat/knowledge_base_chat.py /deploy/code/chat_doc_0918/server/chat/knowledge_base_chat.py.bak-obfix-20260917
sed -i 's|192\.168\.137\.33|192.168.21.111|g' /deploy/code/chat_doc_0918/server/chat/knowledge_base_chat.py
grep -n "192\.168\." /deploy/code/chat_doc_0918/server/chat/knowledge_base_chat.py
cp -a /deploy/code/chat_doc_0918/migrate_to_oceanbase_simple.py /deploy/code/chat_doc_0918/migrate_to_oceanbase_simple.py.bak-obfix-20260917
sed -i "s|'host': '192.168.137.33'|'host': '192.168.21.111'|" /deploy/code/chat_doc_0918/migrate_to_oceanbase_simple.py
sed -i "s|'user': 'root',|'user': 'root@test',|" /deploy/code/chat_doc_0918/migrate_to_oceanbase_simple.py
sed -n '7,15p' /deploy/code/chat_doc_0918/migrate_to_oceanbase_simple.py

echo
echo "=== 3 create tables ==="
cd /deploy/code/chat_doc_0918 || exit 1
source /root/anaconda3/bin/activate recovery
python init_database.py --create-tables 2>&1 | tail -25

echo
echo "=== 4 tables in chat_doc ==="
docker exec oceanbase-ce obclient -h127.1 -P2881 -uroot@test -p12345 -Dchat_doc -e "show tables;" 2>&1 | head -30

echo
echo "=== 5 restart api ==="
systemctl restart chat_doc_api
sleep 80
systemctl is-active chat_doc_api
tail -20 /deploy/cc/logs/api_log.txt 2>&1

echo
echo "=== 6 probes ==="
curl -sk -m 10 -o /dev/null -w "  api /docs HTTP %{http_code}\n" https://127.0.0.1:8261/docs
curl -sk -m 10 -o /dev/null -w "  web       HTTP %{http_code}\n" https://127.0.0.1:3333/

echo
echo "=== 7 speech.rar 内容（决定解压到哪）==="
unrar l /deploy/models/speech.rar 2>&1 | head -25
echo "..."
unrar l /deploy/models/speech.rar 2>&1 | tail -8

echo
echo "=== 8 melo.rar 内容 ==="
unrar l /deploy/models/melo.rar 2>&1 | head -20
