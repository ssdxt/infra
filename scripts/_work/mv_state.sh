#!/bin/bash
MV=/deploy/infra/milvus
echo "########## 1. /deploy/infra/milvus 目录 ##########"
sudo ls -la $MV/

echo
echo "########## 2. data/milvus 目录 ##########"
sudo ls -la $MV/data/milvus/

echo
echo "########## 3. data/milvus/milvus.yaml 现状（storage 相关）##########"
sudo grep -nE "^  storageType:|^    type: minio|^    type: local|^localStorage:|^  path:" $MV/data/milvus/milvus.yaml | head -10

echo
echo "########## 4. 容器状态 / 退出原因 ##########"
sudo docker ps -a --filter name=milvus --format 'table {{.Names}}\t{{.Status}}'
sudo docker inspect milvus-standalone --format 'Exit={{.State.ExitCode}} Error={{.State.Error}} Started={{.State.StartedAt}} Finished={{.State.FinishedAt}}'

echo
echo "########## 5. 容器日志 ##########"
sudo docker logs --tail 30 milvus-standalone 2>&1

echo
echo "########## 6. 当前 fixed compose 的挂载行 ##########"
sudo grep -n "milvus.yaml\|user.yaml\|volumes:" -A2 $MV/docker-compose.fixed.yaml 2>/dev/null | head -20

echo
echo "########## 7. 目录下的 yaml 文件 ##########"
sudo find $MV -maxdepth 2 -name "*.yaml" -o -maxdepth 2 -name "*.yml" 2>/dev/null
