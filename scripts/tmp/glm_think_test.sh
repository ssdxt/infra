#!/bin/bash
KEY="Yv1qFDf-yPxMdXYf_rX1sxm9JyPPAz4pey-z7kviOxU8vNTFOLWvyU0LyyBJI50FgubxHGGrbsQSD9IPywLHIw"
URL="https://api.modelarts-maas.com/v2/chat/completions"
Q='请分析液压系统压力不足的5个可能原因并简要说明排查顺序'
echo "== A) 默认（推理）计时 =="
S=$(date +%s)
curl -s --max-time 120 -X POST "$URL" -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d "{\"model\":\"glm-5.1\",\"messages\":[{\"role\":\"user\",\"content\":\"$Q\"}],\"max_tokens\":200}" -o /tmp/a.json
E=$(date +%s)
echo "elapsed=$((E-S))s"
python3 -c "import json;d=json.load(open('/tmp/a.json'));m=d['choices'][0]['message'];print('reasoning_len=',len(m.get('reasoning_content','')),'content_len=',len(m.get('content','')))"

echo "== B) thinking disabled 计时 =="
S=$(date +%s)
curl -s --max-time 120 -X POST "$URL" -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d "{\"model\":\"glm-5.1\",\"messages\":[{\"role\":\"user\",\"content\":\"$Q\"}],\"max_tokens\":200,\"thinking\":{\"type\":\"disabled\"}}" -o /tmp/b.json
E=$(date +%s)
echo "elapsed=$((E-S))s"
python3 -c "import json;d=json.load(open('/tmp/b.json'));m=d['choices'][0]['message'];print('reasoning_len=',len(m.get('reasoning_content','')),'content_len=',len(m.get('content','')))"
