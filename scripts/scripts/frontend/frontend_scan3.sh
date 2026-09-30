#!/bin/bash
echo "=== work 项目容器是否存在(含停止) ==="
docker ps -a --filter name=one-api --filter name=minio --filter name=mongo --filter name=pg --format "{{.Names}}\t{{.Status}}" 2>/dev/null
docker ps -a | grep -E '\s(redis|mysql|minio|pg|mongo|one-api)\s' 2>/dev/null | awk '{print $NF, $(NF-1), $(NF-2)}' | head -10
echo
echo "=== holarchat 日志 (tail 15) ==="
docker logs holarchat --tail 15 2>&1 | tail -15
echo
echo "=== aippt-minio console 39010 ==="
curl -s -o /dev/null -w "39010 -> %{http_code}\n" --connect-timeout 3 -m 5 http://192.168.21.105:39010/login 2>/dev/null
