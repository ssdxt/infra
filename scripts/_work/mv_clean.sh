#!/bin/bash
MV=/deploy/infra/milvus
B=http://127.0.0.1:19530/v2/vectordb
H='Content-Type: application/json'
TS=$(date +%Y%m%d-%H%M%S)
BK=$MV/backup-$TS

COLS="z_6b26a22d47442fdd3b68b5020de3d35d z_ce94b83fc5b4c35816e099fdaafefc2f z_afd3cdd89459848b196869bce7c5c830 z_05cdba39b524cc0fcfdd37a70a57460a z_78c6e3a56a41c740872305ce15e7c001 images2 chapter_summary"

echo "########## 1. etcd 一致性快照备份 ##########"
sudo mkdir -p "$BK"
sudo docker exec milvus-etcd etcdctl snapshot save /etcd/milvus-etcd-snapshot-$TS.db 2>&1 | tail -3
sudo chmod 644 $MV/data/milvus/volumes/etcd/milvus-etcd-snapshot-$TS.db 2>/dev/null
echo "快照: $(sudo ls -la $MV/data/milvus/volumes/etcd/milvus-etcd-snapshot-$TS.db 2>&1)"

echo
echo "########## 2. 备份 set 前先记录现有 collection ##########"
ORIG=$(curl -s -m 10 -X POST "$B/collections/list" -H "$H" -d '{"dbName":"default"}')
echo "$ORIG" | head -c 500
sudo sh -c "echo '$ORIG' > $BK/collections-before.json"

echo
echo
echo "########## 3. 逐个释放并删除孤儿 collection ##########"
for c in $COLS; do
  curl -s -m 10 -X POST "$B/collections/release" -H "$H" -d "{\"collectionName\":\"$c\"}" >/dev/null 2>&1
  R=$(curl -s -m 20 -X POST "$B/collections/drop" -H "$H" -d "{\"collectionName\":\"$c\"}")
  echo "  drop $c  -> $(echo "$R" | head -c 120)"
done

echo
echo "########## 4. 删除后的 collection 列表 ##########"
curl -s -m 10 -X POST "$B/collections/list" -H "$H" -d '{"dbName":"default"}'
echo

echo
echo "########## 5. 清理本地残留（9月7日的 pprof 等）##########"
sudo ls -la $MV/data/milvus/volumes/milvus/data/ 2>&1
sudo rm -rf $MV/data/milvus/volumes/milvus/data/pprof
echo "已删 pprof"

echo
echo "########## 6. 重启 Milvus 让元数据彻底落定 ##########"
cd $MV || exit 1
sudo docker-compose -f docker-compose.fixed.yaml restart 2>&1 | grep -viE "obsolete|warning" | tail -4
sleep 45

echo
echo "########## 7. 最终状态 ##########"
sudo docker ps --filter name=milvus --format 'table {{.Names}}\t{{.Status}}'
echo "healthz: $(sudo docker exec milvus-standalone curl -s -m 5 http://localhost:9091/healthz 2>/dev/null)"
echo "collections: $(curl -s -m 10 -X POST "$B/collections/list" -H "$H" -d '{"dbName":"default"}')"
echo
echo "备份目录: $BK"
sudo ls -la "$BK"
sudo ls -la $MV/data/milvus/volumes/etcd/*.db 2>&1
