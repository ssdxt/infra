#!/bin/bash
for c in cc-mysql minio cc-redis milvus-standalone cc-nginx portainer milvus-etcd; do
  f=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}' "$c" 2>/dev/null)
  p=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$c" 2>/dev/null)
  echo "$c | project=$p | file=$f"
done
