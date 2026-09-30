#!/bin/bash
B=http://127.0.0.1:19530/v2/vectordb
H='Content-Type: application/json'

echo "########## 1. 列出现有 collection ##########"
curl -s -m 10 -X POST "$B/collections/list" -H "$H" -d '{"dbName":"default"}' | head -c 2000
echo

echo
echo "########## 2. 建一个测试 collection（8 维）##########"
curl -s -m 15 -X POST "$B/collections/create" -H "$H" \
  -d '{"collectionName":"smoke_test_tmp","dimension":8,"metricType":"L2"}' | head -c 500
echo

echo
echo "########## 3. 插入 3 条 ##########"
curl -s -m 15 -X POST "$B/entities/insert" -H "$H" -d '{
  "collectionName":"smoke_test_tmp",
  "data":[
    {"id":1,"vector":[0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1]},
    {"id":2,"vector":[0.2,0.2,0.2,0.2,0.2,0.2,0.2,0.2]},
    {"id":3,"vector":[0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3]}
  ]}' | head -c 500
echo

echo
echo "########## 4. 搜索（查询 [0.1 x8] 最近邻）##########"
curl -s -m 15 -X POST "$B/entities/search" -H "$H" -d '{
  "collectionName":"smoke_test_tmp",
  "data":[[0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1]],
  "limit":3,
  "outputFields":["id"]}' | head -c 800
echo

echo
echo "########## 5. 数据条数 ##########"
curl -s -m 15 -X POST "$B/entities/query" -H "$H" -d '{
  "collectionName":"smoke_test_tmp",
  "filter":"id >= 1",
  "outputFields":["count(*)"],
  "limit":1}' | head -c 400
echo

echo
echo "########## 6. 清理测试 collection ##########"
curl -s -m 15 -X POST "$B/collections/drop" -H "$H" \
  -d '{"collectionName":"smoke_test_tmp"}' | head -c 300
echo

echo
echo "########## 7. 落盘文件 ##########"
sudo find /deploy/infra/milvus/data/milvus/volumes/milvus -type f 2>/dev/null | wc -l
