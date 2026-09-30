#!/bin/bash
echo "=== aippt-agent 日志 (tail 25) ==="
docker logs aippt-agent --tail 25 2>&1 | tail -25
echo
echo "=== 宿主 /data/aippt 目录结构 ==="
find /data/aippt -maxdepth 3 -type f 2>/dev/null | head -40
echo
echo "=== 提取 api 镜像内 /app/configs ==="
CID=$(docker create registry.holardata.com:5100/box/aippt-api-all:generic-0c8e7b 2>/dev/null)
if [ -n "$CID" ]; then
  docker cp "$CID":/app/configs /tmp/api_configs 2>/dev/null && echo "已提取 /app/configs"
  docker rm "$CID" >/dev/null 2>&1
  echo "--- configs 文件清单 ---"
  ls -la /tmp/api_configs/ 2>/dev/null
  echo "--- 包含 18.18.18.60 的文件 ---"
  grep -rn "18.18.18.60" /tmp/api_configs/ 2>/dev/null
  echo "--- nacos/redis 相关配置 ---"
  grep -rn -iE "nacos|redis|36379|8848" /tmp/api_configs/ 2>/dev/null | head -20
fi
echo
echo "=== aippt yaml 中 api 服务完整定义 ==="
awk '/^  api:/,/^  font:/' /data/aippt/docker-compose.yml
