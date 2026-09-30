#!/bin/bash
echo "########## compose 尾部（standalone 之后） ##########"
sudo sed -n '/standalone:/,$p' /deploy/infra/milvus/docker-compose.yaml

echo
echo "########## 另外两个 yaml ##########"
echo "===== milvus_embed_etcd.yaml ====="
sudo cat /deploy/infra/milvus/milvus_embed_etcd.yaml
echo
echo "===== host 上的 milvus.yaml 关键项 ====="
sudo grep -nE "^(etcd|minio|mq|common|rootPath|storageType|address|port|useSSL|accessKeyID|secretAccessKey):" /deploy/infra/milvus/milvus.yaml | head -40

echo
echo "########## 容器状态 ##########"
sudo docker ps -a --filter name=milvus --format 'table {{.Names}}\t{{.Status}}'
sudo docker inspect milvus-standalone --format 'Restarts={{.RestartCount}} Exit={{.State.ExitCode}} Health={{.State.Health.Status}}'

echo
echo "########## milvus-standalone 日志 ##########"
sudo docker logs --tail 100 milvus-standalone 2>&1

echo
echo "########## 网络 ##########"
sudo docker network ls
echo "--- deploy-net ---"
sudo docker network inspect deploy-net --format '{{range .Containers}}{{.Name}} {{.IPv4Address}}{{"\n"}}{{end}}' 2>&1
echo "--- manualai_network 是否存在 ---"
sudo docker network inspect manualai_network --format '{{.Name}}' 2>&1 | head -2

echo
echo "########## 172.18.0.15 通不通 ##########"
timeout 5 bash -c 'cat < /dev/null > /dev/tcp/172.18.0.15/9000' 2>&1 && echo "9000 通" || echo "9000 不通"
