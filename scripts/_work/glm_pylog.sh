#!/bin/bash
C=glm-4-chat-9b

echo "=== 1 mindie 安装目录结构 ==="
docker exec $C ls -la /usr/local/Ascend/mindie/latest/ 2>&1
docker exec $C ls -la /usr/local/Ascend/mindie/latest/mindie-llm/ 2>&1

echo
echo "=== 2 找 pythonlog ==="
docker exec $C sh -c 'ls -la /usr/local/Ascend/mindie/latest/mindie-llm/logs 2>&1'
docker exec $C sh -c 'find /usr/local/Ascend/mindie -name "pythonlog*" 2>/dev/null'
docker exec $C sh -c 'find /root -name "pythonlog*" 2>/dev/null'
docker exec $C sh -c 'find / -maxdepth 4 -name "pythonlog.log" -not -path "/proc/*" 2>/dev/null'

echo
echo "=== 3 pythonlog.log 尾部 150 行 ==="
docker exec $C sh -c 'tail -150 /usr/local/Ascend/mindie/latest/mindie-llm/logs/pythonlog.log 2>&1'

echo
echo "=== 4 pythonlog.log 里的 Error/Traceback ==="
docker exec $C sh -c 'grep -nE "Error|ERROR|Traceback|Exception|raise|failed" /usr/local/Ascend/mindie/latest/mindie-llm/logs/pythonlog.log 2>/dev/null | tail -40'

echo
echo "=== 5 mindie-llm 下所有最近修改的文件 ==="
docker exec $C sh -c 'ls -lat /usr/local/Ascend/mindie/latest/mindie-llm/logs/ 2>&1'

echo
echo "=== 6 /root/mindie 下所有文件 ==="
docker exec $C sh -c 'ls -laR /root/mindie 2>&1'

echo
echo "=== 7 模型权重分片校验（大小是否异常）==="
docker exec $C sh -c 'ls -la /deploy/models/glm-4-9b-chat/ 2>&1 | head -30'
docker exec $C sh -c 'ls /deploy/models/glm-4-9b-chat/model-*.safetensors 2>/dev/null | wc -l'
docker exec $C sh -c 'cat /deploy/models/glm-4-9b-chat/model.safetensors.index.json 2>/dev/null | head -20'
