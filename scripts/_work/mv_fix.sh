#!/bin/bash
MV=/deploy/infra/milvus

echo "########## 1. 停掉旧容器 ##########"
cd $MV || exit 1
sudo docker-compose -f docker-compose.yaml down 2>&1 | grep -viE "obsolete|warning" | tail -5

echo
echo "########## 2. 装修正版 compose ##########"
sudo cp /tmp/docker-compose.fixed.yaml $MV/docker-compose.fixed.yaml
sudo chown root:root $MV/docker-compose.fixed.yaml
sudo docker-compose -f $MV/docker-compose.fixed.yaml config >/dev/null 2>&1 && echo "YAML OK" || echo "YAML 有问题"

echo
echo "########## 3. 启动 ##########"
sudo docker-compose -f docker-compose.fixed.yaml up -d 2>&1 | grep -viE "obsolete|warning" | tail -8

echo
echo "########## 4. 等待并轮询 ##########"
for i in $(seq 1 12); do
  sleep 20
  ST=$(sudo docker ps --filter name=milvus-standalone --format '{{.Status}}')
  ET=$(sudo docker ps --filter name=milvus-etcd --format '{{.Status}}')
  HZ=$(sudo docker exec milvus-standalone curl -s -m 5 http://localhost:9091/healthz 2>/dev/null | head -c 60)
  echo "[$((i*20))s] standalone='$ST' etcd='$ET' healthz='$HZ'"
  if echo "$HZ" | grep -qi "OK"; then echo ">>> Milvus 健康了"; break; fi
done

echo
echo "########## 5. 最近的错误 ##########"
sudo docker logs --tail 300 milvus-standalone 2>&1 | grep -iE "error|fail|panic|unhealthy" | grep -viE "failed to get metrics|service not ready|quotaCenter|proxy client is empty" | tail -15

echo
echo "########## 6. 日志尾部 ##########"
sudo docker logs --tail 15 milvus-standalone 2>&1

echo
echo "########## 7. 数据落盘情况 ##########"
sudo find $MV/data/milvus/volumes/milvus -maxdepth 3 -type d 2>/dev/null | head -15
echo "文件数: $(sudo find $MV/data/milvus/volumes/milvus -type f 2>/dev/null | wc -l)"
