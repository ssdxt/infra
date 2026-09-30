#!/bin/bash
echo "== test model name: qwen3.5 (lowercase) =="
curl -s --max-time 30 -X POST http://172.18.0.120:8020/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3.5","messages":[{"role":"user","content":"hi"}],"max_tokens":8}' \
  | head -c 300; echo
echo "== test model name: Qwen3.5 (uppercase) =="
curl -s --max-time 30 -X POST http://172.18.0.120:8020/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"Qwen3.5","messages":[{"role":"user","content":"hi"}],"max_tokens":8}' \
  | head -c 300; echo
