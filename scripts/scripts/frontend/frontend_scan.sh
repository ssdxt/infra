#!/bin/bash
echo "=== 全部容器及端口映射 ==="
docker ps -a --format "{{.Names}}\t{{.Ports}}\t{{.Status}}" | sed 's/0.0.0.0://g; s/\[::\]://g' | awk -F'\t' '{printf "%-32s %-70s %s\n", $1, $2, $3}'
echo
echo "=== 候选前端端口 HTTP 探测 ==="
for p in 5176 3080 3001 80 8008 8443 19001 2300 8000 8700 9102 8006 9001 35000 18001; do
  code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 -m 5 "http://192.168.21.105:$p/" 2>/dev/null)
  ctype=$(curl -s -I --connect-timeout 3 -m 5 "http://192.168.21.105:$p/" 2>/dev/null | grep -i '^content-type' | tr -d '\r' | awk '{print $2}')
  echo "port $p -> HTTP $code  $ctype"
done
