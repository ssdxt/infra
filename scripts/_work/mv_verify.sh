#!/bin/bash
C=milvus-standalone

cat > /tmp/smoke.py <<'PYEOF'
import sys
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility

connections.connect("default", host="127.0.0.1", port="19530")
print("=== 现有 collection ===")
cols = utility.list_collections()
print("数量:", len(cols))
for c in cols[:20]:
    print("  -", c)

name = "smoke_test_tmp"
if utility.has_collection(name):
    utility.drop_collection(name)

fields = [
    FieldSchema("id",  DataType.INT64, is_primary=True),
    FieldSchema("vec", DataType.FLOAT_VECTOR, dim=8),
]
c = Collection(name, CollectionSchema(fields, description="smoke"))
c.insert([[1, 2, 3], [[0.1]*8, [0.2]*8, [0.3]*8]])
c.create_index("vec", {"index_type": "FLAT", "metric_type": "L2"})
c.load()
r = c.search([[0.1]*8], "vec", {"metric_type": "L2"}, limit=2)
print("=== 搜索结果 ===")
for hit in r[0]:
    print("  id=", hit.id, " dist=", round(hit.distance, 5))
print("=== num_entities ===", c.num_entities)
utility.drop_collection(name)
print(">>> SMOKE TEST PASSED")
PYEOF

echo "########## 1. 容器内是否有 pymilvus ##########"
sudo docker exec $C bash -c 'python3 -c "import pymilvus; print(pymilvus.__version__)"' 2>&1 | tail -2

echo
echo "########## 2. 跑冒烟测试 ##########"
sudo docker cp /tmp/smoke.py $C:/tmp/smoke.py
sudo docker exec $C python3 /tmp/smoke.py 2>&1 | tail -40

echo
echo "########## 3. 状态 ##########"
sudo docker ps --filter name=milvus --format 'table {{.Names}}\t{{.Status}}'
echo "healthz: $(sudo docker exec $C curl -s -m 5 http://localhost:9091/healthz 2>/dev/null)"
echo
echo "19530 端口:"
ss -tln 2>/dev/null | grep 19530 || echo "未监听"
