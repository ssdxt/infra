#!/bin/bash
# 生成测试图并验证 img_server 图片向量化
docker exec img_server python3 -c "from PIL import Image; Image.new('RGB',(64,64),(200,30,30)).save('/ManualAI/Omniknow/code/ai_storage/parser_files/_imgtest.jpg')"
echo "== POST /v1/embeddings/image =="
RESP=$(curl -s --max-time 60 -X POST http://127.0.0.1:18080/v1/embeddings/image \
  -H 'Content-Type: application/json' \
  -d '{"paths":["/ManualAI/Omniknow/code/ai_storage/parser_files/_imgtest.jpg"]}')
echo "$RESP" | head -c 200; echo
echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print('embeddings=',len(d['embeddings']),'dim=',len(d['embeddings'][0]))" 2>&1
echo "== healthz =="
curl -s --max-time 5 http://127.0.0.1:18080/healthz; echo
rm -f /ManualAI/Omniknow/code/ai_storage/parser_files/_imgtest.jpg
