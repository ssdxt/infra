#!/bin/bash
B=http://127.0.0.1:19530/v2/vectordb
H='Content-Type: application/json'

echo "########## 7 个已有 collection 的加载状态 ##########"
for c in z_6b26a22d47442fdd3b68b5020de3d35d z_ce94b83fc5b4c35816e099fdaafefc2f \
         z_afd3cdd89459848b196869bce7c5c830 z_05cdba39b524cc0fcfdd37a70a57460a \
         images2 chapter_summary z_78c6e3a56a41c740872305ce15e7c001; do
  ST=$(curl -s -m 10 -X POST "$B/collections/describe" -H "$H" -d "{\"collectionName\":\"$c\"}" \
       | python3 -c "import sys,json; d=json.load(sys.stdin); print('loadState=',d.get('data',{}).get('loadState'),' rows=',d.get('data',{}).get('numEntities'),' fields=',len(d.get('data',{}).get('fields',[])))" 2>/dev/null \
       || echo "解析失败")
  echo "  $c -> $ST"
done

echo
echo "########## 日志里加载失败的 collection ##########"
sudo docker logs milvus-standalone 2>&1 | grep -oE "collectionID=[0-9]+" | sort -u | head -20

echo
echo "########## 当前错误汇总 ##########"
sudo docker logs --tail 500 milvus-standalone 2>&1 | grep -oE '\[error="[^"]{0,120}' | sort | uniq -c | sort -rn | head -10

echo
echo "########## 容器状态 ##########"
sudo docker ps --filter name=milvus --format 'table {{.Names}}\t{{.Status}}'
