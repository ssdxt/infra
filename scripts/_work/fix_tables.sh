#!/bin/bash
echo "=== 1 fix tilde line (it has trailing spaces) ==="
grep -c '^~' /etc/systemd/system/chat_doc_api.service
sed -i '/^~[[:space:]]*$/d' /etc/systemd/system/chat_doc_api.service
echo "after:"; tail -4 /etc/systemd/system/chat_doc_api.service
systemctl daemon-reload

echo
echo "=== 2 create tables in chat_doc ==="
cd /deploy/code/chat_doc_0918 || exit 1
source /root/anaconda3/bin/activate recovery
echo "python = $(which python)"
python init_database.py --create-tables 2>&1 | tail -35

echo
echo "=== 3 tables now ==="
docker exec oceanbase-ce obclient -h127.1 -P2881 -uroot@test -p12345 -Dchat_doc -e "show tables;" 2>&1 | head -30

echo
echo "=== 4 openapi routes ==="
curl -sk -m 15 -o /tmp/openapi.json https://127.0.0.1:8261/openapi.json
echo -n "size = "; wc -c < /tmp/openapi.json
grep -o '"/[a-zA-Z0-9_/-]*"' /tmp/openapi.json 2>/dev/null | sort -u | head -40

echo
echo "=== 5 embed / rerank endpoints ==="
echo "--- 8105 /v1/embeddings ---"
curl -s -m 25 -X POST http://192.168.21.111:8105/v1/embeddings -H 'Content-Type: application/json' -d '{"input":["hello"],"model":"bge-m3"}' -w '\nHTTP %{http_code}\n' 2>&1 | head -c 400
echo
echo "--- 8105 /embed (native) ---"
curl -s -m 25 -X POST http://192.168.21.111:8105/embed -H 'Content-Type: application/json' -d '{"inputs":"hello"}' -w '\nHTTP %{http_code}\n' 2>&1 | head -c 300
echo
echo "--- 8106 /rerank ---"
curl -s -m 25 -X POST http://192.168.21.111:8106/rerank -H 'Content-Type: application/json' -d '{"query":"hello","texts":["hello","bye"]}' -w '\nHTTP %{http_code}\n' 2>&1 | head -c 400

echo
echo "=== 6 embed containers ==="
docker ps --filter name=embed --filter name=bge-reranker --format '  {{.Names}} | {{.Status}}'
docker logs --tail 6 embed 2>&1 | tail -6
docker logs --tail 6 bge-reranker-v2-m3 2>&1 | tail -6

echo
echo "=== 7 speech status ==="
systemctl is-active chat_doc_speech
echo "--- models dir ---"
ls -la /deploy/models/ 2>&1

echo
echo "=== 8 final ports ==="
ss -lntp 2>/dev/null | grep -E ':(8261|20400|20401|3333|2881|8105|8106|10006)'
