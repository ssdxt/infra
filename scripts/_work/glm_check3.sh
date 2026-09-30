#!/bin/bash
C=glm-4-chat-9b
IMG=swr.cn-south-1.myhuaweicloud.com/ascendhub/mindie:1.0.0-300I-Duo-py11-openeuler24.03-lts

echo "=== 1 MindIE 可能的日志位置 ==="
docker exec $C sh -c 'ls -la /root/ 2>&1 | head -15'
docker exec $C sh -c 'ls -la /root/mindie 2>&1 | head -10'
docker exec $C sh -c 'ls -laR /root/mindie/log 2>&1 | head -30'
docker exec $C sh -c 'ls -la /usr/local/Ascend/mindie/latest/mindie-service/ 2>&1'
docker exec $C sh -c 'ls -la /usr/local/Ascend/mindie/latest/mindie-service/logs 2>&1 | head'

echo
echo "=== 2 mindie-service 目录下所有 log 文件（近期）==="
docker exec $C sh -c 'ls -latR /usr/local/Ascend/mindie/latest/mindie-service/ 2>/dev/null | grep -iE "log$|\.log" | head -20'
docker exec $C sh -c 'ls -la /var/log 2>&1 | head -20'

echo
echo "=== 3 容器内 config.json 全文 ==="
docker exec $C sh -c 'cat /usr/local/Ascend/mindie/latest/mindie-service/conf/config.json'

echo
echo "=== 4 关键：镜像自带的 conf 目录本来有什么（去掉挂载看原貌）==="
docker run --rm --entrypoint /bin/bash \
  swr.cn-south-1.myhuaweicloud.com/ascendhub/mindie:1.0.0-300I-Duo-py311-openeuler24.03-lts \
  -c 'echo "--- 镜像原始 conf/ ---"; ls -la /usr/local/Ascend/mindie/latest/mindie-service/conf/; echo "--- 子目录 ---"; ls -laR /usr/local/Ascend/mindie/latest/mindie-service/conf/ 2>/dev/null | head -40' 2>&1

echo
echo "=== 5 模型目录：分片是否齐全 ==="
ls -la /deploy/models/glm-4-9b-chat/ 2>&1
echo "--- safetensors 分片数 ---"
ls /deploy/models/glm-4-9b-chat/*.safetensors 2>/dev/null | wc -l
echo "--- 模型自带 config.json ---"
cat /deploy/models/glm-4-9b-chat/config.json 2>&1

echo
echo "=== 6 宿主 conf/config.json 完整内容 ==="
cat /deploy/models/glm-4-9b-chat/conf/config.json 2>&1

echo
echo "=== 7 宿主上最新的 plog（进程 705xxx 附近，即容器里的 daemon）==="
ls -lat /root/ascend/log/run/plog/ 2>/dev/null | head -8
P=$(ls -t /root/ascend/log/run/plog/plog-*.log 2>/dev/null | head -1)
echo "latest = $P"
tail -60 "$P" 2>&1

echo
echo "=== 8 有没有 ERROR 级别的 plog ==="
grep -l ERROR /root/ascend/log/run/plog/plog-*.log 2>/dev/null | head -5
for f in $(grep -l ERROR /root/ascend/log/run/plog/plog-*.log 2>/dev/null | head -3); do
  echo "--- $f ---"
  grep -E "ERROR|Error|error" "$f" 2>/dev/null | tail -15
done
