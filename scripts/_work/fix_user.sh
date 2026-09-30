#!/bin/bash
echo "=== 1 grep whole app tree for stale ip ==="
grep -rn "192\.168\.137\.33" /deploy/code/chat_doc_0918 --include=*.py --include=*.json --include=*.yaml --include=*.yml 2>/dev/null | head -20
echo "--- all mysql+pymysql ---"
grep -rn "mysql+pymysql" /deploy/code/chat_doc_0918 --include=*.py 2>/dev/null | head -20
echo "--- create_engine ---"
grep -rn "create_engine" /deploy/code/chat_doc_0918 --include=*.py 2>/dev/null | head -20
echo "--- 8105 / 8106 refs ---"
grep -rn "8105\|8106" /deploy/code/chat_doc_0918 --include=*.py 2>/dev/null | grep -v Binary | head -10

echo
echo "=== 2 migrate_to_oceanbase_simple.py head ==="
sed -n '1,22p' /deploy/code/chat_doc_0918/migrate_to_oceanbase_simple.py

echo
echo "=== 3 test user root (no tenant) ==="
/root/anaconda3/envs/recovery/bin/python -c "import pymysql;c=pymysql.connect(host='192.168.21.111',port=2881,user='root',password='12345',database='chat_doc',connect_timeout=6);print('root -> OK');c.close()" 2>&1 | tail -3

echo "=== 4 test user root@test ==="
/root/anaconda3/envs/recovery/bin/python -c "import pymysql;c=pymysql.connect(host='192.168.21.111',port=2881,user='root@test',password='12345',database='chat_doc',connect_timeout=6);cur=c.cursor();cur.execute('select database()');print('root@test -> OK',cur.fetchone());c.close()" 2>&1 | tail -3

echo
echo "=== 5 show databases as root (sys tenant) ==="
docker exec oceanbase-ce obclient -h127.1 -P2881 -uroot -p12345 -e "show databases;" 2>&1 | head -12

echo
echo "=== 6 show databases as root@test ==="
docker exec oceanbase-ce obclient -h127.1 -P2881 -uroot@test -p12345 -e "show databases;" 2>&1 | head -12

echo
echo "=== 7 rar tools available? ==="
which unrar unar 7z 7za bsdtar unzip 2>&1
ls -la /deploy/models/melo.rar /deploy/models/speech.rar 2>&1

echo
echo "=== 8 speech unit state ==="
systemctl is-active chat_doc_speech
