#!/bin/bash
echo "=== 重建/启动 aippt 栈 ==="
cd /data/aippt && docker-compose up -d 2>&1 | tail -15
echo
echo "=== 重启读取新配置的容器 ==="
docker restart aippt-api aippt-agent aippt-fc aippt-font aippt-web 2>&1
echo
echo "=== 等待 30 秒后查看状态 ==="
sleep 30
docker ps --filter name=aippt --format "{{.Names}}\t{{.Status}}"
