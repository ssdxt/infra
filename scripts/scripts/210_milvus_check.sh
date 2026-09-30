#!/bin/bash
echo '== milvus-etcd 退出日志 =='
docker logs milvus-etcd --tail 15 2>&1
echo
echo '== milvus-standalone 关键 env =='
docker inspect milvus-standalone --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | grep -iE 'etcd|milvus_' | head -10
echo '== compose 里 milvus 相关定义 =='
grep -nA 20 'milvus-etcd:' /ManualAI/OmniKnow/docker-compose.yml | head -28
echo '---- standalone 定义 ----'
grep -nA 25 'milvus-standalone:' /ManualAI/OmniKnow/docker-compose.yml | head -30
