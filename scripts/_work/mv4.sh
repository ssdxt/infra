#!/bin/bash
echo "########## 1. milvus 镜像里有没有 curl（决定 healthcheck 能不能用）##########"
sudo docker run --rm --entrypoint bash swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/milvusdb/milvus:v2.6.9-linuxarm64 \
  -c 'which curl wget nc 2>&1; echo "---"; ls /bin | head -20' 2>&1 | head -25

echo
echo "########## 2. 找可用的 minio arm64 镜像 ##########"
for IMG in \
  "swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/minio/minio:RELEASE.2024-12-18T13-15-44Z" \
  "swr.cn-north-4.myhuaweicloud.com/ddn-k8s/quay.io/minio/minio:RELEASE.2024-12-18T13-15-44Z" \
  "minio/minio:RELEASE.2024-12-18T13-15-44Z" ; do
  echo "=== 尝试 $IMG ==="
  if sudo timeout 180 docker pull "$IMG" 2>&1 | tail -3; then
    echo ">>> 成功: $IMG"
    break
  fi
  echo
done

echo
echo "########## 3. 已有镜像 ##########"
sudo docker images | grep -i minio || echo "无"
