#!/bin/bash
C=glm-4-chat-9b

echo "=========== 1 先看检查逻辑到底查什么 ==========="
docker exec $C sh -c 'sed -n "100,145p" /usr/local/Ascend/atb-models/atb_llm/utils/file_utils.py' 2>&1

echo
echo "=========== 2 修改前的权限链 ==========="
ls -ld /deploy /deploy/models /deploy/models/glm-4-9b-chat 2>&1
echo "--- 模型目录内各项 ---"
find /deploy/models/glm-4-9b-chat -maxdepth 1 -printf '%M %u:%g %p\n' 2>/dev/null | head -30
echo "--- 容器内视角 ---"
docker exec $C sh -c 'ls -ld /deploy /deploy/models /deploy/models/glm-4-9b-chat; id' 2>&1

echo
echo "=========== 3 只摘掉 others 的写权限（o-w）==========="
chmod o-w /deploy 2>/dev/null
chmod o-w /deploy/models 2>/dev/null
chmod -R o-w /deploy/models/glm-4-9b-chat 2>/dev/null
echo "  改完:"
ls -ld /deploy /deploy/models /deploy/models/glm-4-9b-chat 2>&1
echo "  还有没有 others 可写的？(有输出就是还有)"
find /deploy/models/glm-4-9b-chat -perm -o+w 2>/dev/null | head -10
echo "  (以上为空即 OK)"

echo
echo "=========== 4 重启容器 ==========="
docker restart $C 2>&1
echo "  等待 100 秒让 MindIE 加载模型..."
sleep 100

echo
echo "=========== 5 端口 ==========="
ss -lntp 2>/dev/null | grep -E ':10006|:1026|:1027' || echo "  10006/1026/1027 都还没监听"

echo
echo "=========== 6 mindservice.log 尾部 ==========="
docker exec $C sh -c 'tail -25 /usr/local/Ascend/mindie/latest/mindie-service/logs/mindservice.log' 2>&1

echo
echo "=========== 7 mindie-llm 最新进程日志 ==========="
L=$(docker exec $C sh -c 'ls -t /usr/local/Ascend/mindie/latest/mindie-llm/logs/mindie-llm_c_*.log 2>/dev/null | head -1')
echo "  latest = $L"
docker exec $C cat "$L" 2>&1 | tail -40

echo
echo "=========== 8 容器还能活多久 / 进程还在不在 ==========="
docker ps --filter name=$C --format '  {{.Names}} | {{.Status}}'
docker exec $C sh -c 'ps -ef | head -12' 2>&1
