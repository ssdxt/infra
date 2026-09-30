#!/bin/bash
KEY="Yv1qFDf-yPxMdXYf_rX1sxm9JyPPAz4pey-z7kviOxU8vNTFOLWvyU0LyyBJI50FgubxHGGrbsQSD9IPywLHIw"
echo "== chat test glm-5.1 =="
curl -s --max-time 30 -X POST "https://api.modelarts-maas.com/v2/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $KEY" \
  -d '{"model":"glm-5.1","messages":[{"role":"user","content":"hi"}],"max_tokens":8}' \
  | head -c 400; echo
echo "== models list (if supported) =="
curl -s --max-time 15 "https://api.modelarts-maas.com/v2/models" -H "Authorization: Bearer $KEY" | head -c 300
