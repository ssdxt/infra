#!/bin/bash
echo "=== work 项目容器状态 ==="
docker ps --filter name=one-api --filter name=minio --filter name=redis --filter name=pg --filter name=mysql --filter name=mongo --format "{{.Names}}\t{{.Status}}\t{{.Ports}}"
echo
echo "=== 补充探测 ==="
probe() { # $1=描述 $2=url $3=额外curl参数
  code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 -m 6 $3 "$2" 2>/dev/null)
  echo "$1 -> $code"
}
probe "holarchat http 3001"  "http://192.168.21.105:3001/"
probe "holarchat https 3001" "https://192.168.21.105:3001/" "-k"
probe "one-api 2300"         "http://192.168.21.105:2300/"
probe "one-api 2300 /login"  "http://192.168.21.105:2300/login"
probe "2dhuman 8700 http"    "http://192.168.21.105:8700/"
probe "2dhuman 8700 https"   "https://192.168.21.105:8700/" "-k"
probe "minio console 9001"   "http://192.168.21.105:9001/login"
probe "meetnotesai-front 9102 (Host)" "http://192.168.21.105:9102/" "-H 'Host: holardata.com'"
probe "aippt-web 3080 (Host)" "http://192.168.21.105:3080/" "-H 'Host: holardata.com'"
probe "holardataq web 18000" "http://192.168.21.105:18000/"
probe "holardataq api 18001/docs" "http://192.168.21.105:18001/docs"
probe "gwxz 19100 https"     "https://192.168.21.105:19100/" "-k"
probe "windows-arm 8006"     "http://192.168.21.105:8006/"
echo
echo "=== 监听端口确认 ==="
ss -tlnp 2>/dev/null | grep -E ':(3001|2300|8700|9001|9102|18000|18001|8006|19100|5176|19001|8008|3080|80|443)\s' | awk '{print $4, $6}' | sort -u | head -30
