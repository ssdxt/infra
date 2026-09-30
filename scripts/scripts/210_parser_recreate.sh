#!/bin/bash
echo '== 重建 parser / img_service（重读 rag/.env） =='
cd /ManualAI/OmniKnow
docker-compose -f docker-omniknow-fixed.yml up -d parser img_service 2>&1 | tail -4
sleep 15
echo '== 新进程 env 确认 =='
docker exec parser sh -c 'tr "\0" "\n" < /proc/1/environ' 2>/dev/null | grep -E 'MINERU_API|CALLBACK_HOST'
echo '== 复测解析（同一文档 9b000c73） =='
TOKEN=$(curl -s --max-time 15 -X POST http://localhost:8375/api/v1/auth/login -H 'Content-Type: application/json' -d '{"username":"su","password":"YWRtaW4xMjM="}' | grep -oE '"token":"[^"]*"' | head -1 | cut -d'"' -f4)
SPACE=9f7cf8c6-f866-4c58-9cb0-1ecd091c705c
KB=a02b0037-718d-4213-8433-dbc51f49712f
curl -s --max-time 15 -X POST "http://localhost:8375/api/v1/spaces/$SPACE/kbs/$KB/docs/parse" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"doc_ids":["9b000c73-0285-46c1-bfc1-ac1d8e9b7d46"],"parse_config":{"method":"smart","table":true}}' | head -c 250
echo
echo '== 观察 120s（mineru 首次加载模型较慢） =='
sleep 120
echo '--- parser 日志 ---'
tail -8 /ManualAI/OmniKnow/logs/parser.log 2>/dev/null | sed -e 's/\x1b\[[0-9;]*m//g'
echo '--- aiserver 任务 ---'
grep -aE "任务 [0-9a-f-]+ \|" /ManualAI/OmniKnow/logs/aiserver.log 2>/dev/null | sed -e 's/\x1b\[[0-9;]*m//g' | tail -3
echo '--- mineru 日志 ---'
docker logs mineru-api --tail 6 2>&1 | tail -6
