cat > /tmp/neo_body2.json <<'EOF'
{"messages":[{"role":"user","content":"请分析液压系统压力不足的5个可能原因，并简要说明排查顺序"}],"locale":"zh-CN","thread_id":"06a9e5e4-2477-720e-8000-50aeb4acaf5d","resources":[],"enable_longterm_memory":false,"user_id":"194fcade-b65a-4bc2-9371-831c0ca41da7","image_url":"","llm_type":"basic","mcp_settings":{}}
EOF
START=$(date +%s)
timeout 120 curl -s -N -X POST "http://127.0.0.1:8378/knowledge_api/api/neo/chat/stream" \
  -H "Content-Type: application/json" --data @/tmp/neo_body2.json -o /tmp/neo_resp2.txt
END=$(date +%s)
echo "elapsed=$((END-START))s bytes=$(wc -c < /tmp/neo_resp2.txt)"
docker cp /tmp/neo_resp2.txt assistant:/tmp/neo_resp2.txt 2>/dev/null
docker exec assistant /root/anaconda3/envs/assistant/bin/python -c "import json
txt=[]; reason=[]
for line in open('/tmp/neo_resp2.txt',encoding='utf-8'):
    line=line.strip()
    if line.startswith('data: '):
        try: d=json.loads(line[6:])
        except Exception: continue
        if d.get('content'): txt.append(d['content'])
        if d.get('reasoning_content'): reason.append(d['reasoning_content'])
print('content_len=',len(''.join(txt)),'reason_len=',len(''.join(reason)))
print('content_preview=', ''.join(txt)[:150])"
