#!/bin/bash
F=/ManualAI/OmniKnow/omniknow2/parser/rag/parser/utils.py
cp "$F" "$F.bak.$(date +%H%M%S)"
sed -i 's|img_service_base_url = "http://192.168.0.23:18080"|img_service_base_url = f"http://img_service:{IMG_SERVICE_PORT}"|' "$F"
grep -n 'img_service_base_url' "$F"
echo '== 语法检查 =='
docker exec parser /root/anaconda3/envs/parser/bin/python -c "import ast; ast.parse(open('/ManualAI/OmniKnow/omniknow2/parser/rag/parser/utils.py', encoding='utf-8').read()); print('OK')"
echo '== 重启 parser =='
docker restart parser 2>&1
sleep 12
echo '== 重新触发解析(文档 9b000c73) =='
TOKEN=$(curl -s --max-time 15 -X POST http://localhost:8375/api/v1/auth/login -H 'Content-Type: application/json' -d '{"username":"su","password":"YWRtaW4xMjM="}' | grep -oE '"token":"[^"]*"' | head -1 | cut -d'"' -f4)
curl -s --max-time 15 -X POST "http://localhost:8375/api/v1/spaces/9f7cf8c6-f866-4c58-9cb0-1ecd091c705c/kbs/a02b0037-718d-4213-8433-dbc51f49712f/docs/parse" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"doc_ids":["9b000c73-0285-46c1-bfc1-ac1d8e9b7d46"],"parse_config":{"method":"smart","table":true}}' | head -c 250
echo
echo '== 完成，等待结果(另行查询) =='
