#!/bin/bash
C=glm-4-chat-9b
SVC=/usr/local/Ascend/mindie/latest/mindie-service

echo "=== 1 mindservice.log 全文 ==="
docker exec $C cat $SVC/logs/mindservice.log 2>&1

echo
echo "=== 2 mindie_audit.log 全文 ==="
docker exec $C cat $SVC/logs/mindie_audit.log 2>&1

echo
echo "=== 3 /var/log/mindie_log ==="
docker exec $C ls -la /var/log/mindie_log/ 2>&1
docker exec $C sh -c 'tail -60 /var/log/mindie_log/* 2>/dev/null' 2>&1 | head -80

echo
echo "=== 4 /var/log/cann_atb_log ==="
docker exec $C ls -la /var/log/cann_atb_log/ 2>&1
docker exec $C sh -c 'tail -40 /var/log/cann_atb_log/* 2>/dev/null' 2>&1 | head -60

echo
echo "=== 5 nputools_LOG_INFO.log ==="
docker exec $C cat /var/log/nputools_LOG_INFO.log 2>&1

echo
echo "=== 6 conf 目录现状（对照镜像原貌）==="
docker exec $C sh -c 'ls -la /usr/local/Ascend/mindie/latest/mindie-service/conf/'

echo
echo "=== 7 daemon 重启了几次（脑裂证据）==="
docker exec $C sh -c 'ls -la /root/mindie/log/debug/ 2>&1'

echo
echo "=== 8 直接手工拉起 daemon，实时抓 30 秒输出 ==="
docker exec $C sh -c 'cd /usr/local/Ascend/mindie/latest/mindie-service && timeout 25 ./bin/mindieservice_daemon 2>&1 | head -60'

echo
echo "=== 9 手工拉起后端口有没有起来 ==="
ss -lntp 2>/dev/null | grep -E ':10006|:1026|:1027' || echo "  10006/1026/1027 都没有监听"
