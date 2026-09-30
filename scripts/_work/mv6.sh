#!/bin/bash
MV=/deploy/infra/milvus
SRC=$MV/data/milvus/milvus.yaml

echo "########## 1. 现有数据（判断能不能清）##########"
sudo find $MV/data/milvus/volumes/milvus -type f 2>/dev/null | head -10
echo "文件数: $(sudo find $MV/data/milvus/volumes/milvus -type f 2>/dev/null | wc -l)"
echo "--- etcd 元数据里的 bucket 痕迹 ---"
sudo timeout 15 docker exec milvus-etcd etcdctl --endpoints=localhost:2379 get --prefix by-dev/ --keys-only 2>/dev/null | grep -ciE "bucket|minio|a-bucket" || true

echo
echo "########## 2. 确认要改的键各出现几次 ##########"
echo "storageType: remote  -> $(sudo grep -c '^  storageType: remote' $SRC)"
echo "woodpecker type minio-> $(sudo grep -c '^    type: minio # The Type of the storage provider' $SRC)"
echo "etcd use embed       -> $(sudo grep -n 'embed:' $SRC | head -3)"

echo
echo "########## 3. 生成改好的配置 ##########"
sudo cp $SRC $MV/milvus.local.yaml
sudo sed -i 's|^  storageType: remote.*|  storageType: local # 改为本地文件系统，不再依赖 MinIO/S3|' $MV/milvus.local.yaml
sudo sed -i 's|^    type: minio # The Type of the storage provider.*|    type: local # 改为本地文件系统|' $MV/milvus.local.yaml
echo "--- 校验改动 ---"
sudo grep -n "storageType:\|^    type: local\|^localStorage:\|^  path:" $MV/milvus.local.yaml | head -10
sudo sed -n '/^woodpecker:/,/^pulsar:/p' $MV/milvus.local.yaml | grep -nE "storage:|type:|rootPath:"

echo
echo "########## 4. minio 镜像拉取情况 ##########"
tail -3 /tmp/minio_pull.log 2>/dev/null || echo "无日志"
sudo docker images | grep -i minio || echo "还没拉到"
