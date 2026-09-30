#!/bin/bash
PDF=/ManualAI/Omniknow/code/parser/rag/parser/test_case/test.pdf
echo "== trigger mineru file_parse =="
START=$(date +%s)
RESP=$(curl -s --max-time 200 -X POST http://127.0.0.1:8000/file_parse \
  -F "file=@$PDF" -F "start=0" -F "end=1")
END=$(date +%s)
echo "elapsed=$((END-START))s"
echo "$RESP" | head -c 500; echo
echo "$RESP" | wc -c
echo "== mineru gpu usage =="
nvidia-smi --query-compute-apps=pid,used_memory --format=csv 2>/dev/null | tail -6
