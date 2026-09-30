#!/bin/bash
set -u
MV=/deploy/infra/milvus
Y=$MV/data/milvus/milvus.yaml
B=http://127.0.0.1:19530/v2/vectordb
H='Content-Type: application/json'
TS=$(date +%Y%m%d-%H%M%S)

echo "########## 1. 清掉被误建成目录的 milvus.local.yaml ##########"
sudo rm -rf $MV/milvus.local.yaml

echo
echo "########## 2. 备份原始配置，再就地改成 local 存储 ##########"
sudo cp -a $Y $Y.bak-$TS
echo "备份: $Y.bak-$TS"

sudo sed -i 's|^  storageType: remote.*|  storageType: local # 本地文件系统，不依赖 MinIO/S3|' $Y
sudo sed -i 's|^    type: minio # The Type of the storage provider.*|    type: local # 本地文件系统|' $Y

echo "--- 校验改动 ---"
sudo grep -n "^  storageType:" $Y
sudo sed -n '/^woodpecker:/,/^pulsar:/p' $Y | grep -nE "storage:|^    type:|rootPath:"
sudo grep -n "^localStorage:" -A2 $Y | head -5

echo
echo "########## 3. 更新 compose 挂载 ##########"
sudo cp /tmp/docker-compose.fixed.yaml $MV/docker-compose.fixed.yaml
sudo chown root:root $MV/docker-compose.fixed.yaml
sudo grep -n "milvus.yaml" $MV/docker-compose.fixed.yaml
sudo docker-compose -f $MV/docker-compose.fixed.yaml config >/dev/null 2>&1 && echo "YAML OK" || echo "YAML 有问题"

echo
echo "########## 4. 启动 ##########"
cd $MV || exit 1
sudo docker-compose -f docker-compose.fixed.yaml up -d --force-recreate 2>&1 | grep -viE "obsolete|warning" | tail -6

echo
echo "########## 5. 等待健康 ##########"
for i in $(seq 1 10); do
  sleep 20
  ST=$(sudo docker ps --filter name=milvus-standalone --format '{{.Status}}')
  HZ=$(sudo docker exec milvus-standalone curl -s -m 5 http://localhost:9091/healthz 2>/dev/null)
  echo "[$((i*20))s] '$ST' healthz='$HZ'"
  if echo "$HZ" | grep -qi OK; then break; fi
done

echo
echo "########## 6. 功能验证 ##########"
echo "collections: $(curl -s -m 10 -X POST "$B/collections/list" -H "$H" -d '{"dbName":"default"}')"
echo "--- 建表 ---"
curl -s -m 15 -X POST "$B/collections/create" -H "$H" \
  -d '{"collectionName":"final_check","dimension":8,"metricType":"L2"}'
echo
echo "--- 插入 ---"
curl -s -m 15 -X POST "$B/entities/insert" -H "$H" -d '{
  "collectionName":"final_check",
  "data":[{"id":1,"vector":[0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1]},
          {"id":2,"vector":[0.9,0.9,0.9,0.9,0.9,0.9,0.9,0.9]}]}'
echo
echo "--- 搜索 ---"
curl -s -m 15 -X POST "$B/entities/search" -H "$H" -d '{
  "collectionName":"final_check",
  "data":[[0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1]],
  "limit":2,"outputFields":["id"]}'
echo
echo "--- 清理测试表 ---"
curl -s -m 15 -X POST "$B/collections/drop" -H "$H" -d '{"collectionName":"final_check"}'
echo

echo
echo "########## 7. 残留错误检查 ##########"
echo "load 失败条数: $(sudo docker logs milvus-standalone 2>&1 | grep -icE 'invalid local path|LoadDeltaLogs|load segment failed')"

echo
echo "########## 8. 最终状态 ##########"
sudo docker ps --filter name=milvus --format 'table {{.Names}}\t{{.Status}}'
echo "collections: $(curl -s -m 10 -X POST "$B/collections/list" -H "$H" -d '{"dbName":"default"}')"
echo
echo "--- 目录 ---"
sudo ls -la $MV/
echo "--- data/milvus ---"
sudo ls -la $MV/data/milvus/
