#!/bin/bash
# 纯只读探路
echo "########## 1. 找 dockerun / docker_run 目录 ##########"
ls -d /deploy/model* 2>/dev/null
ls -d /deploy/models/docker_run 2>/dev/null
ls -d /deploy/model/dockerun 2>/dev/null
echo "--- 全盘找 compose 文件（深度 5）---"
find /deploy -maxdepth 5 -name "docker-compose*.y*ml" -o -maxdepth 5 -name "compose*.y*ml" 2>/dev/null | sort

echo
echo "########## 2. /deploy/models/docker_run 目录结构 ##########"
ls -laR /deploy/models/docker_run/ 2>/dev/null | head -40

echo
echo "########## 3. 如果存在 /deploy/model ##########"
ls -laR /deploy/model/ 2>/dev/null | head -30

echo
echo "########## 4. 当前容器 ##########"
docker ps -a --format '  {{.ID}}  {{.Names}}  {{.Status}}  {{.Image}}' 2>&1

echo
echo "########## 5. 当前镜像 ##########"
docker images --format '  {{.Repository}}:{{.Tag}}  {{.ID}}  {{.Size}}' 2>&1

echo
echo "########## 6. NPU 占用 ##########"
npu-smi info 2>&1 | head -25

echo
echo "########## 7. NPU 上的进程 ##########"
npu-smi info 2>&1 | sed -n '/Process id/,$p'
