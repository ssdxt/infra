#!/bin/bash
echo "=== aippt-api 日志 (tail 30) ==="
docker logs aippt-api --tail 30 2>&1 | tail -30
echo
echo "=== aippt-agent 日志 (tail 12) ==="
docker logs aippt-agent --tail 12 2>&1 | tail -12
echo
echo "=== 接口连通性测试 ==="
for u in "http://192.168.21.105:39071/" "http://192.168.21.105:39005/" "http://192.168.21.105:39002/" "http://192.168.21.105:35000/"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 -m 8 "$u" 2>/dev/null)
  echo "$u -> HTTP $code"
done
echo
echo "=== 1分钟后容器状态(确认不再重启) ==="
sleep 60
docker ps --filter name=aippt --format "{{.Names}}\t{{.Status}}"
