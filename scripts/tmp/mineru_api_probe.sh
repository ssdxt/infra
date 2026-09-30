#!/bin/bash
echo "== find file_parse endpoint =="
docker exec mineru-api sh -c 'grep -rn "file_parse\|def parse\|UploadFile\|File(" /opt/venv/lib/python3.12/site-packages/mineru/application/api 2>/dev/null | head -20'
echo "== openapi file_parse params =="
curl -s http://127.0.0.1:8000/openapi.json | python3 -c "
import sys, json
d = json.load(sys.stdin)
for p, item in d['paths'].items():
    if 'parse' in p or 'file' in p:
        print(p, list(item.keys()))
        for m, op in item.items():
            if m == 'post':
                rb = op.get('requestBody', {})
                schema = rb.get('content', {}).get('multipart/form-data', {}).get('schema', {})
                print('  body schema:', schema)
" 2>&1 | head -20
