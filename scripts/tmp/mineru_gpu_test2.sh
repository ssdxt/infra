#!/bin/bash
PDF=/ManualAI/Omniknow/code/parser/rag/parser/test_case/test.pdf
echo "== trigger parse =="
START=$(date +%s)
RESP=$(curl -s --max-time 240 -X POST http://127.0.0.1:8000/file_parse \
  -F "files=@$PDF" -F "files=@$PDF" \
  -F "backend=hybrid-auto-engine" -F "start_page_id=0" -F "end_page_id=1")
END=$(date +%s)
echo "elapsed=$((END-START))s  bytes=$(echo "$RESP" | wc -c)"
echo "$RESP" | head -c 400; echo
echo "== mineru in gpu? =="
nvidia-smi --query-compute-apps=pid,used_memory --format=csv 2>/dev/null | tail -8
echo "== mineru log tail =="
docker logs mineru-api --tail 8 2>&1 | tail -8
