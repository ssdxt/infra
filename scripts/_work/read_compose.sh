#!/bin/bash
echo "########## 1. bge-m3 compose ##########"
echo "--- /deploy/models/docker_run/bge-m3/ ---"
ls -la /deploy/models/docker_run/bge-m3/
echo
echo "===== docker-compose.yml ====="
cat /deploy/models/docker_run/bge-m3/docker-compose.yml

echo
echo "############################################################"
echo "########## 2. vllm compose ##########"
echo "--- /deploy/models/docker_run/vllm/ ---"
ls -la /deploy/models/docker_run/vllm/
echo
echo "===== docker-compose.yml ====="
cat /deploy/models/docker_run/vllm/docker-compose.yml

echo
echo "############################################################"
echo "########## 3. 当前 glm-4-9b-chat 容器配置（占用显存的那个）##########"
docker inspect glm-4-9b-chat --format 'Image: {{.Config.Image}}
Cmd: {{json .Config.Cmd}}
Entrypoint: {{json .Config.Entrypoint}}
Runtime: {{.HostConfig.Runtime}}
Devices: {{json .HostConfig.Devices}}
Binds: {{json .HostConfig.Binds}}
ShmSize: {{.HostConfig.ShmSize}}' 2>&1

echo
echo "########## 4. 该容器内的 mindie config 关键项 ##########"
docker exec glm-4-9b-chat bash -c 'grep -nE "npuDeviceIds|worldSize|modelName|modelWeightPath|maxSeqLen|maxInputTokenLen|npuMemSize|port\"" /usr/local/Ascend/mindie/latest/mindie-service/conf/config.json 2>/dev/null' 2>&1 | head -20

echo
echo "########## 5. 现有镜像 ##########"
docker images --format '  {{.Repository}}:{{.Tag}}  {{.ID}}  {{.Size}}' 2>&1

echo
echo "########## 6. 可能的启动脚本 ##########"
ls -la /deploy/cc/bash/ 2>/dev/null | head -20
echo "--- /deploy/cc/service ---"
ls -la /deploy/cc/service/ 2>/dev/null
