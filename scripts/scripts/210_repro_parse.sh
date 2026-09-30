#!/bin/bash
TOKEN=$(curl -s --max-time 15 -X POST http://localhost:8375/api/v1/auth/login -H 'Content-Type: application/json' -d '{"username":"su","password":"YWRtaW4xMjM="}' | grep -oE '"token":"[^"]*"' | head -1 | cut -d'"' -f4)
SPACE=9f7cf8c6-f866-4c58-9cb0-1ecd091c705c
KB=a02b0037-718d-4213-8433-dbc51f49712f
SRC=$(ls /ManualAI/OmniKnow/omniknow2/server/tmp/parser/*/*/documents/source/*.pdf 2>/dev/null | head -1)
echo "测试文件: $SRC"
[ -z "$SRC" ] && { echo '无现成 pdf'; exit 1; }
cp "$SRC" /tmp/repro.pdf

echo '== 1. 上传 =='
UP=$(curl -s --max-time 30 -X POST "http://localhost:8375/api/v1/spaces/$SPACE/kbs/$KB/docs/upload" -H "Authorization: Bearer $TOKEN" -F "files=@/tmp/repro.pdf")
echo "$UP" | head -c 400
echo
DOCID=$(echo "$UP" | grep -oE '"uuid":"[0-9a-f-]{36}"' | head -1 | cut -d'"' -f4)
echo "doc id: $DOCID"
if [ -z "$DOCID" ]; then echo '上传未返回 uuid，退出'; exit 1; fi

echo '== 2. 触发解析 =='
curl -s --max-time 15 -X POST "http://localhost:8375/api/v1/spaces/$SPACE/kbs/$KB/docs/parse" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "{\"doc_ids\":[\"$DOCID\"],\"parse_config\":{\"method\":\"smart\",\"table\":true}}" | head -c 300
echo

echo '== 3. 等待并观察结果(70s) =='
sleep 70
echo '--- aiserver 任务日志 ---'
grep -aE "任务 $|文件解析|上传文件" /ManualAI/OmniKnow/logs/aiserver.log 2>/dev/null | sed -e 's/\x1b\[[0-9;]*m//g' | tail -5
echo '--- parser 日志 ---'
tail -6 /ManualAI/OmniKnow/logs/parser.log 2>/dev/null | sed -e 's/\x1b\[[0-9;]*m//g'
echo '--- mineru 日志尾 ---'
docker logs mineru-api --tail 5 2>&1 | tail -5
