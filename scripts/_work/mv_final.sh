#!/bin/bash
MV=/deploy/infra/milvus
B=http://127.0.0.1:19530/v2/vectordb
H='Content-Type: application/json'

echo "########## 0. 把 etcd 快照挪到备份目录（不留在数据目录里）##########"
BK=$(sudo ls -d $MV/backup-* 2>/dev/null | tail -1)
sudo mv $MV/data/milvus/volumes/etcd/milvus-etcd-snapshot-*.db "$BK"/ 2>/dev/null
sudo ls -la "$BK"

echo
echo "########## 1. 日志里还有没有 load 失败 ##########"
CNT=$(sudo docker logs milvus-standalone 2>&1 | grep -icE "invalid local path|LoadDeltaLogs|load segment failed|failed to load some segments")
echo "残留错误条数: $CNT"

echo
echo "########## 2. 完整读写冒烟测试 ##########"
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
echo "--- 持久化验证：重启后数据还在吗 ---"
cd $MV && sudo docker-compose -f docker-compose.fixed.yaml restart standalone 2>&1 | grep -viE "obsolete|warning" | tail -2
sleep 40
echo "重启后 healthz: $(sudo docker exec milvus-standalone curl -s -m 5 http://localhost:9091/healthz 2>/dev/null)"
echo "重启后 collections: $(curl -s -m 10 -X POST "$B/collections/list" -H "$H" -d '{"dbName":"default"}')"
echo "重启后 数据条数: $(curl -s -m 15 -X POST "$B/entities/query" -H "$H" -d '{"collectionName":"final_check","filter":"id >= 1","outputFields":["count(*)"],"limit":1}')"

echo
echo "--- 清理测试表 ---"
curl -s -m 15 -X POST "$B/collections/drop" -H "$H" -d '{"collectionName":"final_check"}'
echo

echo
echo "########## 3. 最终状态 ##########"
sudo docker ps --filter name=milvus --format 'table {{.Names}}\t{{.Status}}'
echo "collections: $(curl -s -m 10 -X POST "$B/collections/list" -H "$H" -d '{"dbName":"default"}')"
echo
echo "########## 4. 磁盘占用 ##########"
sudo du -sh $MV/data/milvus/volumes/etcd $MV/data/milvus/volumes/milvus 2>/dev/null
df -h /deploy | tail -1
