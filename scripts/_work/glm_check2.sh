#!/bin/bash
C=glm-4-chat-9b

echo "=== 0 这个容器是哪个 compose 起的 ==="
docker inspect -f '{{json .Config.Labels}}' $C 2>&1

echo
echo "=== 1 容器内 / 目录（找 glm-4.log）==="
docker exec $C ls -la / 2>&1

echo
echo "=== 2 容器内 /glm-4.log ==="
docker exec $C sh -c 'ls -la /glm-4.log 2>&1; echo "----- tail 80 -----"; tail -80 /glm-4.log 2>&1'

echo
echo "=== 3 容器内进程 ==="
docker exec $C sh -c 'ps -ef 2>&1 | head -20'

echo
echo "=== 4 容器内 mindie conf 目录（看是不是被整目录挂载遮蔽了）==="
docker exec $C sh -c 'ls -la /usr/local/Ascend/mindie/latest/mindie-service/conf/ 2>&1'

echo
echo "=== 5 容器内 config.json 关键项 ==="
docker exec $C sh -c 'F=/usr/local/Ascend/mindie/latest/mindie-service/conf/config.json; ls -la $F; grep -nE "npuDeviceIds|worldSize|modelName|modelWeightPath|maxSeqLen|npuMemSize|port|httpsEnabled|openAiSupport" $F 2>&1 | head -25'

echo
echo "=== 6 容器内设备 ==="
docker exec $C sh -c 'ls -la /dev/davinci0 /dev/davinci1 /dev/davinci_manager /dev/devmm_svm /dev/hisi_hdc 2>&1'

echo
echo "=== 7 容器内 npu-smi ==="
docker exec $C sh -c '/usr/local/sbin/npu-smi info 2>&1 | head -12'

echo
echo "=== 8 容器内端口监听 ==="
docker exec $C sh -c 'ss -lntp 2>&1 | head -12'

echo
echo "=== 9 宿主侧 conf 与模型目录权限 ==="
ls -la /deploy/models/glm-4-9b-chat/conf/ 2>&1
echo "--- 模型根目录 ---"
ls -la /deploy/models/glm-4-9b-chat/ 2>&1 | head -12

echo
echo "=== 10 最新 plog ==="
ls -lat /root/ascend/log/run/plog/ 2>/dev/null | head -6
P=$(ls -t /root/ascend/log/run/plog/plog-*.log 2>/dev/null | head -1)
echo "--- tail 50 of $P ---"
tail -50 "$P" 2>&1

echo
echo "=== 11 有没有别的 mindie/glm 进程在宿主上 ==="
ps -ef | grep -iE "mindie|glm|mindieservice" | grep -v grep | head -10 || echo "  无"
