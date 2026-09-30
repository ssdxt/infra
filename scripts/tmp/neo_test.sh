cat > /tmp/neo_body.json <<'EOF'
{"messages":[{"role":"user","content":"你好"}],"locale":"zh-CN","thread_id":"06a9e5e4-2477-720e-8000-50aeb4acaf5d","resources":[],"enable_longterm_memory":false,"user_id":"194fcade-b65a-4bc2-9371-831c0ca41da7","image_url":"","llm_type":"basic","mcp_settings":{}}
EOF
echo "== curl neo/chat/stream (llm_type=basic), 90s cap =="
START=$(date +%s)
timeout 90 curl -s -N -X POST "http://127.0.0.1:8378/knowledge_api/api/neo/chat/stream" \
  -H "Content-Type: application/json" \
  -H "Referer: http://113.44.11.210:8378/" \
  --data @/tmp/neo_body.json \
  -o /tmp/neo_resp.txt
END=$(date +%s)
echo "elapsed=$((END-START))s  bytes=$(wc -c < /tmp/neo_resp.txt)"
echo "== resp head =="
head -c 800 /tmp/neo_resp.txt; echo
