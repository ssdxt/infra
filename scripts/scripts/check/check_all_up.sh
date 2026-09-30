#!/bin/bash
echo "=== 运行中: $(docker ps -q | wc -l) / 总数: $(docker ps -aq | wc -l) ==="
echo
echo "=== 全部容器状态 ==="
docker ps -a --format '{{.Names}} | {{.Status}}' | sort
echo
echo "=== 是否有 Restarting(崩溃循环) ==="
docker ps -a --format '{{.Names}} | {{.Status}}' | grep -iE 'restarting|unhealthy' || echo "无"
echo
echo "=== 关键端口连通性 ==="
for p in 3306 5432 2300 9001 5176 3080 3001 8008 19001 18000 39071 17199 6208 8001 5000 8333; do
  code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 2 -m 4 "http://192.168.21.105:$p/" 2>/dev/null)
  printf "%-6s %s\n" "$p" "$code"
done
