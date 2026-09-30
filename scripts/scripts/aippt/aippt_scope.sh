#!/bin/bash
echo "=== /data/aippt 下所有含 18.18.18.60 的配置文件(排除mysql数据) ==="
grep -rln "18.18.18.60" /data/aippt --exclude-dir=mysql 2>/dev/null
echo
echo "=== 各文件出现次数 ==="
for f in $(grep -rln "18.18.18.60" /data/aippt --exclude-dir=mysql 2>/dev/null); do
  echo "$f : $(grep -c '18.18.18.60' "$f") 处"
done
echo
echo "=== font/.env.prod 是否含 IP ==="
grep -n -E '18\.18\.18\.60|39011|39002|39004' /data/aippt/font/.env.prod 2>/dev/null | head -10
echo
echo "=== api/agent 容器所在网络 ==="
docker inspect aippt-api --format 'networks: {{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null
docker inspect aippt-agent --format 'networks: {{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null
docker inspect aippt-redis --format 'networks: {{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null
docker inspect aippt-nacos --format 'networks: {{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null
