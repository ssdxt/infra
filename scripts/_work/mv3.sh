#!/bin/bash
MV=/deploy/infra/milvus
Y1=$MV/data/milvus/milvus.yaml     # 实际挂载进容器的
Y2=$MV/milvus.yaml                 # 目录里另一个

echo "########## 1. yaml 里有没有硬编码网段 ##########"
sudo grep -n "172\.18\.\|172\.30\.\|172\.17\." $Y1 | head -20
echo "--- 另一个文件 ---"
sudo grep -n "172\.18\.\|172\.30\.\|172\.17\." $Y2 | head -20
echo "(空=没有硬编码)"

echo
echo "########## 2. 挂载版 milvus.yaml 的 etcd/minio/mq 段 ##########"
sudo sed -n '/^etcd:/,/^[a-z]/p' $Y1 | grep -vE "^\s*#" | grep -E ":" | head -20
echo "--- minio ---"
sudo sed -n '/^minio:/,/^[a-z]/p' $Y1 | grep -vE "^\s*#" | head -25
echo "--- mq ---"
sudo sed -n '/^mq:/,/^[a-z]/p' $Y1 | grep -vE "^\s*#" | head -20
echo "--- common 里的地址相关 ---"
sudo sed -n '/^common:/,/^[a-z]/p' $Y1 | grep -vE "^\s*#" | grep -iE "address|port|localRpc|security|ttl" | head -15

echo
echo "########## 3. data 目录 / minio 是否存在 ##########"
sudo ls -la $MV/data/
echo "--- volumes/milvus ---"
sudo ls -la $MV/data/milvus/volumes/milvus/ 2>&1 | head
echo "--- volumes/etcd/member ---"
sudo find $MV/data/milvus/volumes/etcd -maxdepth 2 2>&1 | head

echo
echo "########## 4. 宿主上有没有 minio 容器/数据 ##########"
sudo docker ps -a --format '{{.Names}}' | grep -i minio || echo "无 minio 容器"
sudo find /deploy -maxdepth 4 -iname "*minio*" 2>/dev/null | head

echo
echo "########## 5. etcd 里是否残留旧 session (172.18.x) ##########"
sudo timeout 20 docker exec milvus-etcd etcdctl --endpoints=localhost:2379 get --prefix by-dev/meta/session/ 2>&1 | head -20
echo "--- etcd 所有 key 数 ---"
sudo timeout 20 docker exec milvus-etcd etcdctl --endpoints=localhost:2379 get --prefix by-dev/ --keys-only 2>&1 | wc -l

echo
echo "########## 6. 192.168.21.111 上 9000/9002 端口有没有服务 ##########"
ss -tln 2>/dev/null | grep -E ':9000|:9002|:9003' || echo "本机没有 9000 端口"
