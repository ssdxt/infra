#!/bin/bash
echo "=== llm.holardata.com 解析(宿主机) ==="
getent hosts llm.holardata.com || echo "宿主机无法解析"
echo "=== portal 容器内解析 ==="
docker exec holaros-portal getent hosts llm.holardata.com 2>/dev/null || echo "容器内无法解析"
echo
echo "=== one-api 是否空库(fresh) ==="
docker logs one-api --tail 8 2>&1 | tail -8
echo
echo "=== one-api 登录测试 admin/123456 ==="
curl -s -X POST http://192.168.21.105:2300/api/user/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"123456"}' --connect-timeout 3 -m 6 | head -c 200
echo
echo "=== one-api 通道列表(用token) ==="
TOKEN=$(curl -s -X POST http://192.168.21.105:2300/api/user/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"123456"}' 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('access_token',''))" 2>/dev/null)
echo "token: ${TOKEN:0:20}..."
if [ -n "$TOKEN" ]; then
  curl -s http://192.168.21.105:2300/api/channel/?p=1 -H "Authorization: Bearer $TOKEN" --connect-timeout 3 -m 6 | head -c 400
  echo
fi
echo
echo "=== holar_portal 库表 ==="
docker exec holaros-mysql mysql -uroot -pholar_mysql_root -e "SHOW DATABASES" 2>/dev/null | head -15
docker exec holaros-mysql mysql -uroot -pholar_mysql_root holar_portal -e "SHOW TABLES" 2>/dev/null | grep -iE 'model|llm|config|chat' | head -15
