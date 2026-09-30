#!/bin/bash
echo "########## 1. /deploy/infra/milvus 目录 ##########"
sudo ls -laR /deploy/infra/milvus/ 2>&1 | head -40

echo
echo "########## 2. compose 文件 ##########"
for f in /deploy/infra/milvus/*.yml /deploy/infra/milvus/*.yaml; do
  echo "===== $f ====="
  sudo cat "$f"
  echo
done

echo
echo "########## 3. 容器状态 ##########"
sudo docker ps -a --filter name=milvus --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
sudo docker inspect milvus-standalone --format 'Restarts={{.RestartCount}} Exit={{.State.ExitCode}} OOM={{.State.OOMKilled}} Health={{.State.Health.Status}} Failing={{range .State.Health.Log}}{{.ExitCode}} {{end}}'

echo
echo "########## 4. milvus-standalone 日志 ##########"
sudo docker logs --tail 80 milvus-standalone 2>&1
