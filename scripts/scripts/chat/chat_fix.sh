#!/bin/bash
NEWKEY="sk-d8L3tFOqR51W03k1BcA1E4BfF6Ef49E3B7A4F34eAf4b3e80"
echo "=== 更新前 id=46 的 key ==="
docker exec holaros-mysql mysql -uroot -pholar_mysql_root holar_portal -N -e "SELECT JSON_UNQUOTE(JSON_EXTRACT(config,'\$.api_key')) FROM models WHERE id=46" 2>/dev/null
echo
echo "=== 执行 UPDATE ==="
docker exec holaros-mysql mysql -uroot -pholar_mysql_root holar_portal -e "UPDATE models SET config=JSON_SET(config,'\$.api_key','$NEWKEY'), updated_at=NOW() WHERE id=46" 2>/dev/null && echo "更新完成"
echo
echo "=== 更新后 id=46 的 key ==="
docker exec holaros-mysql mysql -uroot -pholar_mysql_root holar_portal -N -e "SELECT JSON_UNQUOTE(JSON_EXTRACT(config,'\$.api_key')) FROM models WHERE id=46" 2>/dev/null
echo
echo "=== 用新 key 实测 chat 接口 ==="
curl -s --connect-timeout 5 -m 30 "http://llm.holardata.com:2300/v1/chat/completions" -H "Authorization: Bearer $NEWKEY" -H "Content-Type: application/json" -d '{"model":"Qwen3.5-397B-A17B","messages":[{"role":"user","content":"你好，回复一句话"}],"max_tokens":50}' | head -c 500
