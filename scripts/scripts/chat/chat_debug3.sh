#!/bin/bash
echo "=== models 表全部内容 ==="
docker exec holaros-mysql mysql -uroot -pholar_mysql_root holar_portal -e "SELECT id, name, model_name, api_base, api_key, status FROM models\G" 2>/dev/null | head -80
echo
echo "=== 实测公网网关 key 有效性 ==="
KEY=$(docker exec holaros-mysql mysql -uroot -pholar_mysql_root holar_portal -N -e "SELECT api_key FROM models WHERE id=46 LIMIT 1" 2>/dev/null)
echo "id=46 key: ${KEY:0:12}...(长度 ${#KEY})"
if [ -n "$KEY" ]; then
  curl -s --connect-timeout 5 -m 10 "http://llm.holardata.com:2300/v1/models" -H "Authorization: Bearer $KEY" | head -c 300
  echo
fi
echo
echo "=== 公网网关连通性(不带key) ==="
curl -s -o /dev/null -w "llm.holardata.com:2300 -> HTTP %{http_code}\n" --connect-timeout 5 -m 8 "http://llm.holardata.com:2300/v1/models" 2>/dev/null
