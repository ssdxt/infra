#!/bin/bash
KEY37=$(docker exec holaros-mysql mysql -uroot -pholar_mysql_root holar_portal -N -e "SELECT JSON_UNQUOTE(JSON_EXTRACT(config,'\$.api_key')) FROM models WHERE id=37" 2>/dev/null)
KEY46=$(docker exec holaros-mysql mysql -uroot -pholar_mysql_root holar_portal -N -e "SELECT JSON_UNQUOTE(JSON_EXTRACT(config,'\$.api_key')) FROM models WHERE id=46" 2>/dev/null)
echo "id=37 key: ${KEY37:0:16}... (len ${#KEY37})"
echo "id=46 key: ${KEY46:0:16}... (len ${#KEY46})"
echo
echo "=== 测试 id=37 key 调 /v1/models ==="
curl -s --connect-timeout 5 -m 12 "http://llm.holardata.com:2300/v1/models" -H "Authorization: Bearer $KEY37" | head -c 400
echo
echo "=== 测试 id=46 key 调 /v1/models ==="
curl -s --connect-timeout 5 -m 12 "http://llm.holardata.com:2300/v1/models" -H "Authorization: Bearer $KEY46" | head -c 400
echo
echo "=== 测试 id=46 key 调 chat 接口 ==="
curl -s --connect-timeout 5 -m 15 "http://llm.holardata.com:2300/v1/chat/completions" -H "Authorization: Bearer $KEY46" -H "Content-Type: application/json" -d '{"model":"Qwen3.5-397B-A17B","messages":[{"role":"user","content":"hi"}],"max_tokens":10}' | head -c 400
echo
echo "=== 机器上其他配置里有没有 sk- key ==="
grep -rn -oE 'sk-[A-Za-z0-9]{20,}' /root/box_manager /root/work/holaros /data/aippt /root/apps 2>/dev/null --include='*.yaml' --include='*.yml' --include='*.json' --include='*.conf' --include='*.env' --include='*.js' 2>/dev/null | head -10
